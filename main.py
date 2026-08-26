from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import FeatureNotFound
from bs4.exceptions import ParserRejectedMarkup
from requests import RequestException

from collectors.html_collector import collect_html
from core.environment import configure_ssl
from core.run_lock import AlreadyRunningError, single_instance_lock
from processing.deduplicator import remove_duplicates
from collectors.rss_collector import collect_rss
from config import (
    CONDITIONAL_SERIOUS_TOPICS,
    CONTEXTUAL_TOPICS,
    DRY_RUN,
    EXCLUDE_KEYWORDS,
    MAX_NEWS_PER_RUN,
    MIN_PUBLICATION_SCORE,
    NEWS_LOOKBACK_DAYS,
    POST_MODE,
    SCORE_RULES,
    SERIOUS_OUTCOME_KEYWORDS,
    SOURCES,
    STRONG_TOPICS,
    TOPICS,
)
from processing.filters import (
    add_scores,
    calculate_score,
    filter_by_date,
    filter_by_minimum_score,
    filter_by_topics,
    sort_by_score,
)
from publishing.telegram import (
    ImageDownloadError,
    download_image_temp,
    send_telegram_photo,
    send_telegram_post,
)
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


# Финальный PNG можно добавить отдельно: отсутствие файла безопасно
# переводит публикацию на обычный sendMessage.
FALLBACK_BANNER_PATH = (
    Path(__file__).resolve().parent
    / "assets"
    / "livecrime_fallback_banner.png"
)

# Короткий список ловит только очевидные служебные картинки сайтов.
# Его намеренно не расширяем до агрессивного blacklist всех URL.
SERVICE_IMAGE_MARKERS = (
    "logo",
    "placeholder",
    "default_image",
    "default-image",
    "noimage",
    "no-image",
)


def is_usable_article_image(image_url):
    """Отбрасывает отсутствующие и очевидно служебные image URL."""

    if not isinstance(image_url, str) or not image_url.strip():
        return False

    # Маркеры проверяем в URL-пути и имени файла без параметров запроса.
    image_path = unquote(urlsplit(image_url).path).casefold()
    return not any(marker in image_path for marker in SERVICE_IMAGE_MARKERS)


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
            print(
                "[PHOTO] image_url found: "
                f"{'yes' if news_item.get('image_url') else 'no'}"
            )
            continue

        # Пустое значение включает fallback на RSS description.
        news_item.setdefault("article_text", "")

        # None явно показывает, что основная картинка пока не найдена.
        news_item.setdefault("image_url", None)

        try:
            # Страницу загружаем один раз для текста и картинки.
            html = fetch_article_html(news_item["url"])

            if not news_item.get("article_text"):
                extracted_text = extract_article_text(
                    html,
                    source=news_item.get("source"),
                )
                article_text = clean_article_text(
                    extracted_text,
                    source=news_item.get("source"),
                )
                news_item["article_text"] = article_text

            if not news_item.get("image_url"):
                news_item["image_url"] = extract_article_image_url(
                    html,
                    news_item["url"],
                )

            print(
                "[PHOTO] image_url found: "
                f"{'yes' if news_item.get('image_url') else 'no'}"
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


def print_selected_diagnostics(selected_news):
    """Показывает, почему каждая новость дошла до публикации."""

    for news_item in selected_news:
        print("SELECTED:")
        print(f"Заголовок: {news_item['title']}")
        print(f"Matched topics: {news_item.get('matched_topics', [])}")
        print(f"Serious topics: {news_item.get('strong_topics', [])}")
        print(
            "Contextual topics: "
            f"{news_item.get('contextual_topics', [])}"
        )
        print(f"Score: {news_item.get('score', 0)}")
        print(
            "Причина допуска: "
            f"{news_item.get('admission_reason', 'не указана')}"
        )
        print()


def print_rejected_diagnostics(news_items, score_rules, limit=5):
    """Показывает несколько лучших отклонённых кандидатов в DRY_RUN."""

    rejected_news = []

    for news_item in news_items:
        # Материалы вообще без тематических совпадений не засоряют лог.
        if not news_item.get("matched_topics"):
            continue

        if news_item.get("strict_filter_passed") and (
            news_item.get("score", 0) >= MIN_PUBLICATION_SCORE
        ):
            continue

        # Для strict-rejected материалов score нужен только для диагностики.
        news_item.setdefault(
            "score",
            calculate_score(news_item, score_rules),
        )
        rejected_news.append(news_item)

    rejected_news.sort(key=lambda item: item["score"], reverse=True)

    for news_item in rejected_news[:limit]:
        print("REJECTED:")
        print(f"Заголовок: {news_item['title']}")
        print(f"Причина: {news_item.get('rejection_reason', 'не указана')}")
        print(f"Score: {news_item['score']}")
        print()


def print_ranked_diagnostics(ranked_news, limit=10):
    """Показывает лучшие допустимые новости без увеличения лимита постов."""

    print(f"TOP {min(limit, len(ranked_news))} CANDIDATES:")

    for position, news_item in enumerate(ranked_news[:limit], start=1):
        print(f"{position}. Источник: {news_item.get('source', 'не указан')}")
        print(f"   Заголовок: {news_item['title']}")
        print(f"   Serious topics: {news_item.get('strong_topics', [])}")
        print(
            "   Contextual topics: "
            f"{news_item.get('contextual_topics', [])}"
        )
        print(f"   Score: {news_item.get('score', 0)}")

    print()


def publish_selected_news(
    selected_news,
    history,
    dry_run,
    post_mode,
    send_post=send_telegram_post,
    send_photo=send_telegram_photo,
    download_image=download_image_temp,
    add_history=add_to_history,
    fallback_banner_path=None,
):
    """Формирует и по одному разу обрабатывает выбранные посты."""

    history_changed = False
    total_posts = len(selected_news)

    # Это единственный цикл публикации и единственная точка отправки.
    for post_number, news_item in enumerate(selected_news, start=1):
        post = generate_post(news_item)
        image_url = news_item.get("image_url")
        usable_image_url = (
            image_url if is_usable_article_image(image_url) else None
        )
        banner_path = (
            Path(fallback_banner_path)
            if fallback_banner_path is not None
            else None
        )
        photo_caption = generate_photo_caption(news_item)
        print("=" * 60)
        print(
            "[PHOTO] image_url found: "
            f"{'yes' if image_url else 'no'}"
        )
        print(
            "[PHOTO] article image usable: "
            f"{'yes' if usable_image_url else 'no'}"
        )

        if image_url and not usable_image_url:
            print(f"[PHOTO] service image rejected: {image_url}")

        # В DRY_RUN Telegram API и история вообще не вызываются.
        if dry_run:
            matched_topics = news_item.get("matched_topics", [])
            print(f"Темы: {', '.join(matched_topics)}")

            if usable_image_url:
                print(f"[DRY RUN] Photo URL: {usable_image_url}")
                print("[DRY RUN] Caption:")
                print(photo_caption)
            elif banner_path is not None and banner_path.is_file():
                print("[DRY RUN] Selected image source: fallback banner")
                print(f"[DRY RUN] Banner: {banner_path}")
                print("[DRY RUN] Caption:")
                print(photo_caption)
            else:
                print("[DRY RUN] Photo URL: NOT FOUND")
                print("[DRY RUN] Fallback banner: NOT FOUND")
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

        if usable_image_url:
            print("[PHOTO] trying remote URL")
            photo_result = send_photo(
                usable_image_url,
                photo_caption,
            )
            publication_succeeded = bool(photo_result)
            publication_uncertain = getattr(
                photo_result,
                "uncertain",
                False,
            )

            if publication_succeeded:
                print("[PHOTO] remote URL success")
            elif publication_uncertain:
                # При ReadTimeout Telegram мог уже создать сообщение.
                # Не делаем fallback, чтобы не получить второй пост.
                print(
                    "[PHOTO] result: delivery status unknown; "
                    "no retry or fallback to prevent duplicate"
                )
            elif getattr(photo_result, "remote_fetch_failed", False):
                # File fallback нужен только когда Telegram явно сообщил,
                # что не смог самостоятельно получить remote URL.
                print("[PHOTO] Telegram cannot fetch remote URL")
                print("[PHOTO] downloading image to temporary file")

                temporary_image = None

                try:
                    temporary_image = download_image(usable_image_url)
                    downloaded_kb = temporary_image.size_bytes / 1024
                    print(
                        f"[PHOTO] downloaded: {temporary_image.mime_type}, "
                        f"{downloaded_kb:.0f} KB"
                    )
                    print("[PHOTO] trying multipart upload")

                    # Файл открывается только на время одного sendPhoto.
                    with temporary_image.path.open("rb") as image_file:
                        file_result = send_photo(
                            image_file,
                            photo_caption,
                            filename=temporary_image.path.name,
                            mime_type=temporary_image.mime_type,
                        )

                    publication_succeeded = bool(file_result)
                    publication_uncertain = getattr(
                        file_result,
                        "uncertain",
                        False,
                    )

                    if publication_succeeded:
                        print("[PHOTO] multipart upload success")
                    elif publication_uncertain:
                        # После ReadTimeout повтор также может создать дубль.
                        print(
                            "[PHOTO] multipart result unknown; "
                            "no sendMessage fallback to prevent duplicate"
                        )
                    else:
                        error_reason = getattr(
                            file_result,
                            "error_reason",
                            "причина не указана",
                        )
                        print("[PHOTO] multipart upload failed")
                        print(f"[PHOTO] Причина: {error_reason}")
                        print("[PHOTO] fallback to sendMessage")

                except ImageDownloadError as error:
                    # Непригодная картинка не мешает отправить текст новости.
                    print(f"[PHOTO] temporary download failed: {error}")
                    print("[PHOTO] fallback to sendMessage")

                except OSError as error:
                    # Ошибка временного файла также является подтверждённым
                    # отсутствием пригодной картинки на стороне runner-а.
                    print(
                        "[PHOTO] temporary file failed: "
                        f"{type(error).__name__}"
                    )
                    print("[PHOTO] fallback to sendMessage")

                finally:
                    # Temporary file никогда не остаётся в репозитории
                    # или на runner-е после завершения этой попытки.
                    if (
                        temporary_image is not None
                        and temporary_image.path.exists()
                    ):
                        temporary_image.path.unlink()
                        print("[PHOTO] temporary file removed")
            else:
                # Подтверждённая несвязанная ошибка не запускает скачивание.
                attempts = getattr(photo_result, "attempts", 1)
                error_reason = getattr(
                    photo_result,
                    "error_reason",
                    "причина не указана",
                )
                print(
                    f"[PHOTO] sendPhoto failed after {attempts} "
                    "attempt(s), "
                    "fallback to sendMessage"
                )
                print(f"[PHOTO] Причина: {error_reason}")
                print(f"[PHOTO] Image URL: {usable_image_url}")

        else:
            if image_url:
                print("[PHOTO] article image is not usable")
            elif banner_path is None:
                # Сохраняем прежнюю диагностику для явно отключённого banner.
                print("[PHOTO] image_url not found, using sendMessage")
            else:
                print("[PHOTO] image_url not found")

        # Banner допустим только до первой отправки либо после подтверждённой
        # безопасной ошибки. Неопределённый timeout сюда не попадёт.
        if not publication_succeeded and not publication_uncertain:
            if banner_path is None:
                print("[PHOTO] fallback banner disabled")
            else:
                try:
                    # Локальный PNG отправляется напрямую как multipart.
                    # Никакой внешний hosting или второй download не нужен.
                    with banner_path.open("rb") as banner_file:
                        print("[PHOTO] trying local fallback banner")
                        banner_result = send_photo(
                            banner_file,
                            photo_caption,
                            filename=banner_path.name,
                            mime_type="image/png",
                        )

                    publication_succeeded = bool(banner_result)
                    publication_uncertain = getattr(
                        banner_result,
                        "uncertain",
                        False,
                    )

                    if publication_succeeded:
                        print("[PHOTO] fallback banner success")
                    elif publication_uncertain:
                        # Telegram мог принять banner: sendMessage создаст дубль.
                        print(
                            "[PHOTO] fallback banner result unknown; "
                            "no sendMessage fallback to prevent duplicate"
                        )
                    else:
                        error_reason = getattr(
                            banner_result,
                            "error_reason",
                            "причина не указана",
                        )
                        print("[PHOTO] fallback banner failed")
                        print(f"[PHOTO] Причина: {error_reason}")
                        print("[PHOTO] fallback to sendMessage")

                except FileNotFoundError:
                    print(
                        "[PHOTO] fallback banner not found: "
                        f"{banner_path}"
                    )
                    print("[PHOTO] fallback to sendMessage")

                except OSError as error:
                    # Нечитаемый asset не должен останавливать весь запуск.
                    print(
                        "[PHOTO] fallback banner cannot be read: "
                        f"{type(error).__name__}"
                    )
                    print("[PHOTO] fallback to sendMessage")

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
            elif image_url or banner_path is not None:
                print("Публикация не удалась. История не изменена.")
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
        SERIOUS_OUTCOME_KEYWORDS,
        STRONG_TOPICS,
        CONTEXTUAL_TOPICS,
        CONDITIONAL_SERIOUS_TOPICS,
    )
    add_scores(topic_news, SCORE_RULES)
    publication_news = filter_by_minimum_score(
        topic_news,
        MIN_PUBLICATION_SCORE,
    )
    ranked_news = sort_by_score(publication_news, SCORE_RULES)

    # Event dedup сравнивает title с началом реального article_text.
    # Загружаем hard-filter кандидатов до дедупликации; выбранная статья
    # затем использует уже сохранённые article_text/image_url без повтора.
    load_selected_article_text(ranked_news)
    unique_news = remove_duplicates(ranked_news, debug=DRY_RUN)
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

    print(f"Всего собрано новостей: {len(all_news)}")
    print(f"За последние {NEWS_LOOKBACK_DAYS} дня: {len(fresh_news)}")
    print(f"После hard serious-crime filter: {len(topic_news)}")
    print(
        "После MIN_PUBLICATION_SCORE "
        f"({MIN_PUBLICATION_SCORE}): {len(publication_news)}"
    )
    print(f"После удаления дублей: {len(unique_news)}")
    print(f"Новых новостей: {len(new_news)}")
    print(f"Выбрано для публикации: {len(selected_news)}")
    print()

    print_selected_diagnostics(selected_news)

    # В безопасном режиме показываем только несколько полезных отказов.
    if DRY_RUN:
        print_ranked_diagnostics(ranked_news)
        print_rejected_diagnostics(fresh_news, SCORE_RULES)

    history_changed = publish_selected_news(
        selected_news,
        history,
        DRY_RUN,
        POST_MODE,
        fallback_banner_path=FALLBACK_BANNER_PATH,
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
