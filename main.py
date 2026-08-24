from bs4 import FeatureNotFound
from bs4.exceptions import ParserRejectedMarkup
from requests import RequestException

from collectors.html_collector import collect_html
from core.environment import configure_ssl
from core.run_lock import AlreadyRunningError, single_instance_lock
from processing.deduplicator import remove_duplicates
from collectors.rss_collector import collect_rss
from config import (
    CRIME_CONTEXT_KEYWORDS,
    DRY_RUN,
    EXCLUDE_KEYWORDS,
    MAX_NEWS_PER_RUN,
    NEWS_LOOKBACK_DAYS,
    POST_MODE,
    SCORE_RULES,
    SOURCES,
    TOPICS,
)
from processing.filters import (
    filter_by_date,
    filter_by_topics,
    sort_by_score,
)
from publishing.telegram import send_telegram_photo, send_telegram_post
from storage.history import (
    add_to_history,
    is_published,
    load_history,
    save_history,
)
from generation.post_generator import generate_photo_caption, generate_post

from article.fetcher import (
    clean_article_text,
    extract_article_image_url,
    extract_article_text,
    fetch_article_html,
)


def collect_enabled_news():
    """Собирает материалы только из включённых источников."""

    # Отсутствующий enabled означает True для обратной совместимости.
    active_sources = [
        source for source in SOURCES
        if source.get("enabled", True)
    ]
    disabled_count = len(SOURCES) - len(active_sources)

    print(f"Активных источников: {len(active_sources)}")
    print(f"Отключённых источников: {disabled_count}")
    print()

    all_news = []

    for source in active_sources:
        # RSS и HTML используют разные collectors,
        # но возвращают одинаковые словари news_item.
        if source["type"] == "rss":
            news_items = collect_rss(source)

        elif source["type"] == "html":
            news_items = collect_html(source)

        else:
            print(
                f"Предупреждение: неизвестный тип источника "
                f"{source['type']!r}."
            )
            continue

        print(f"Источник: {source['name']}")
        print(f"Найдено новостей: {len(news_items)}")
        print()

        # Дальше pipeline уже не различает RSS и HTML.
        all_news.extend(news_items)

    return all_news


def load_selected_article_text(selected_news):
    """Загружает текст и URL картинки каждой выбранной новости."""

    for news_item in selected_news:
        # Повторный HTTP-запрос не нужен, если оба результата уже обработаны.
        # Наличие image_url со значением None означает, что картинки не было.
        if (
            "article_text" in news_item
            and "image_url" in news_item
        ):
            continue

        # Пустое значение включает fallback на RSS description.
        news_item.setdefault("article_text", "")

        # None явно показывает, что основная картинка пока не найдена.
        news_item.setdefault("image_url", None)

        try:
            # Страницу загружаем один раз для текста и картинки.
            html = fetch_article_html(news_item["url"])

            if not news_item.get("article_text"):
                extracted_text = extract_article_text(html)
                article_text = clean_article_text(extracted_text)
                news_item["article_text"] = article_text

            if not news_item.get("image_url"):
                news_item["image_url"] = extract_article_image_url(
                    html,
                    news_item["url"],
                )

        # Ошибка одной страницы не останавливает остальные статьи.
        except (
            RequestException,
            FeatureNotFound,
            ParserRejectedMarkup,
        ) as error:
            print("Предупреждение: не удалось обработать статью.")
            print(f"Заголовок: {news_item['title']}")
            print(f"URL: {news_item['url']}")
            print(f"Причина: {error}")
            print()
            continue

        if not news_item["article_text"]:
            print("Предупреждение: текст статьи не найден.")
            print(f"Заголовок: {news_item['title']}")
            print(f"URL: {news_item['url']}")
            print()
            continue

        # Текст и картинка остаются привязаны к одному news_item.


def publish_selected_news(
    selected_news,
    history,
    dry_run,
    post_mode,
    send_post=send_telegram_post,
    send_photo=send_telegram_photo,
    add_history=add_to_history,
):
    """Формирует и по одному разу обрабатывает выбранные посты."""

    history_changed = False
    total_posts = len(selected_news)

    # Это единственный цикл публикации и единственная точка отправки.
    for post_number, news_item in enumerate(selected_news, start=1):
        post = generate_post(news_item)
        image_url = news_item.get("image_url")
        photo_caption = generate_photo_caption(news_item)
        print("=" * 60)

        # В DRY_RUN Telegram API и история вообще не вызываются.
        if dry_run:
            matched_topics = news_item.get("matched_topics", [])
            print(f"Темы: {', '.join(matched_topics)}")

            if image_url:
                print(f"[DRY RUN] Photo URL: {image_url}")
                print("[DRY RUN] Caption:")
                print(photo_caption)
            else:
                print("[DRY RUN] Photo URL: NOT FOUND")
                print("[DRY RUN] Текстовый пост:")
                print(post)

            print()
            continue

        if post_mode != "single":
            print(f"Ошибка: режим POST_MODE={post_mode!r} не поддерживается.")
            print()
            continue

        # Номер, заголовок и URL позволяют проверить одну публикацию новости.
        print(f"[TELEGRAM] Отправка {post_number}/{total_posts}")
        print(f"Заголовок: {news_item['title']}")
        print(f"URL: {news_item['url']}")

        publication_succeeded = False
        publication_uncertain = False

        if image_url:
            print("Пробуем отправить одно сообщение через sendPhoto.")
            photo_result = send_photo(
                image_url,
                photo_caption,
            )
            publication_succeeded = bool(photo_result)
            publication_uncertain = getattr(
                photo_result,
                "uncertain",
                False,
            )

            if publication_succeeded:
                print("Пост с изображением успешно отправлен в Telegram.")
            elif publication_uncertain:
                # При ReadTimeout Telegram мог уже создать сообщение.
                # Не делаем fallback, чтобы не получить второй пост.
                print(
                    "[TELEGRAM] sendPhoto result uncertain, "
                    "fallback disabled to prevent duplicate"
                )
            else:
                # Если Telegram не получил картинку, сохраняем текстовый путь.
                attempts = getattr(photo_result, "attempts", 1)
                print(
                    f"[TELEGRAM] sendPhoto failed after {attempts} "
                    "attempt(s), "
                    "fallback to sendMessage"
                )

        else:
            print(
                "[TELEGRAM] image_url not found, using sendMessage"
            )

        if not publication_succeeded and not publication_uncertain:
            post_result = send_post(post)
            publication_succeeded = bool(post_result)
            publication_uncertain = getattr(
                post_result,
                "uncertain",
                False,
            )

            if publication_succeeded:
                print("Текстовый пост успешно отправлен в Telegram.")
            elif publication_uncertain:
                print(
                    "[TELEGRAM] sendMessage result uncertain, "
                    "automatic repeat disabled"
                )

        if publication_succeeded:
            # Независимо от способа публикации добавляем одну запись истории.
            add_history(news_item, history)
            history_changed = True

        else:
            if publication_uncertain:
                print(
                    "Результат отправки не подтверждён. "
                    "История не изменена."
                )
            elif image_url:
                print("Оба способа не сработали. История не изменена.")
            else:
                print("Текстовый пост не отправлен. История не изменена.")

        print()

    return history_changed


def run():
    """Запускает полный pipeline LiveCrime один раз."""

    # Настраиваем CA bundle до первого сетевого запроса.
    configure_ssl()
    all_news = collect_enabled_news()

    fresh_news = filter_by_date(all_news, NEWS_LOOKBACK_DAYS)
    topic_news = filter_by_topics(
        fresh_news,
        TOPICS,
        EXCLUDE_KEYWORDS,
        CRIME_CONTEXT_KEYWORDS,
    )
    ranked_news = sort_by_score(topic_news, SCORE_RULES)
    unique_news = remove_duplicates(ranked_news)
    history = load_history()

    # В DRY_RUN история не ограничивает повторные тесты.
    if DRY_RUN:
        new_news = unique_news.copy()
    else:
        new_news = [
            news_item for news_item in unique_news
            if not is_published(news_item, history)
        ]

    selected_news = new_news[:MAX_NEWS_PER_RUN]
    load_selected_article_text(selected_news)

    print(f"Всего собрано новостей: {len(all_news)}")
    print(f"За последние {NEWS_LOOKBACK_DAYS} дня: {len(fresh_news)}")
    print(f"Подходят по тематике: {len(topic_news)}")
    print(f"После удаления дублей: {len(unique_news)}")
    print(f"Новых новостей: {len(new_news)}")
    print(f"Выбрано для публикации: {len(selected_news)}")
    print()

    history_changed = publish_selected_news(
        selected_news,
        history,
        DRY_RUN,
        POST_MODE,
    )

    # Все успешные добавления сохраняются одним вызовом после цикла.
    if not DRY_RUN and history_changed:
        save_history(history)


if __name__ == "__main__":
    try:
        # Второй параллельный процесс не сможет отправить ту же выборку.
        with single_instance_lock():
            run()
    except AlreadyRunningError:
        print("LiveCrime уже запущен. Повторный запуск остановлен.")
