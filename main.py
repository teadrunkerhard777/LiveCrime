from bs4 import FeatureNotFound
from bs4.exceptions import ParserRejectedMarkup
from requests import RequestException

from collectors.html_collector import collect_html
from core.environment import configure_ssl
from processing.deduplicator import remove_duplicates
from collectors.rss_collector import collect_rss
from config import (
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
from publishing.telegram import send_telegram_post
from storage.history import (
    add_to_history,
    is_published,
    load_history,
    save_history,
)
from generation.post_generator import generate_post

from article.fetcher import (
    clean_article_text,
    extract_article_text,
    fetch_article_html,
)


# Один раз указываем стандартной библиотеке актуальный CA bundle.
# Это выполняется до первого RSS или HTML-запроса.
configure_ssl()


# Здесь будем собирать новости со всех источников.
all_news = []

# Проходим по каждому источнику из config.py.
for source in SOURCES:
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

    # После этого места общий pipeline уже не различает RSS и HTML.
    all_news.extend(news_items)


# Оставляем только новости за последние N дней.
fresh_news = filter_by_date(
    all_news,
    NEWS_LOOKBACK_DAYS,
)


# Оставляем только новости,
# подходящие по тематике канала.
topic_news = filter_by_topics(
    fresh_news,
    TOPICS,
    EXCLUDE_KEYWORDS,
)

# Сортируем подходящие новости
# по рейтингу интересности.
ranked_news = sort_by_score(
    topic_news,
    SCORE_RULES,
)

# Убираем повторяющиеся новости.
unique_news = remove_duplicates(ranked_news)

# Загружаем историю уже обработанных новостей.
history = load_history()


# В тестовом режиме история не ограничивает выборку.
# Копия списка позволяет повторно проверять одни и те же новости,
# даже если их URL уже сохранены в published.json.
if DRY_RUN:
    new_news = unique_news.copy()

# В рабочем режиме история защищает канал от повторных публикаций.
else:
    new_news = []

    # Проверяем каждую новость по сохранённой истории
    # и оставляем только ещё не опубликованные материалы.
    for news_item in unique_news:
        if not is_published(news_item, history):
            new_news.append(news_item)


# Ограничиваем количество новостей,
# которые попадут в текущую подборку.
selected_news = new_news[:MAX_NEWS_PER_RUN]

# Загружаем основной текст для каждой выбранной новости.
# Каждый результат сохраняется в тот же news_item, где лежат URL и заголовок.
for news_item in selected_news:
    # Если текст уже был успешно получен, второй HTTP-запрос не нужен.
    if news_item.get("article_text"):
        continue

    # Пустое значение заранее включает безопасный fallback
    # на RSS description в генераторе поста.
    news_item["article_text"] = ""

    try:
        # Все этапы используют URL именно текущего news_item.
        html = fetch_article_html(news_item["url"])
        extracted_text = extract_article_text(html)
        article_text = clean_article_text(extracted_text)

    # Ошибка одной страницы не должна останавливать остальные новости.
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

    # Пустая страница тоже не считается успешным результатом.
    if not article_text:
        print("Предупреждение: текст статьи не найден.")
        print(f"Заголовок: {news_item['title']}")
        print(f"URL: {news_item['url']}")
        print()
        continue

    # Сохраняем текст именно в текущую новость.
    # Это исключает смешивание разных заголовков, URL и статей.
    news_item["article_text"] = article_text

print(f"Всего собрано новостей: {len(all_news)}")
print(
    f"За последние {NEWS_LOOKBACK_DAYS} дня: "
    f"{len(fresh_news)}"
)
print(f"Подходят по тематике: {len(topic_news)}")
print(f"После удаления дублей: {len(unique_news)}")
print(f"Новых новостей: {len(new_news)}")
print(f"Выбрано для публикации: {len(selected_news)}")
print()


# Отмечаем, нужно ли сохранить историю после всех отправок.
# Файл записываем один раз, только если хотя бы один пост ушёл успешно.
history_changed = False

# В режиме single каждая новость формирует отдельный Telegram-пост.
for news_item in selected_news:
    post = generate_post(news_item)

    print("=" * 60)

    # В DRY_RUN показываем готовый пост, но даже не вызываем
    # функцию Telegram. История при этом тоже не меняется.
    if DRY_RUN:
        print("[DRY RUN] Пост не отправлен в Telegram")
        matched_topics = news_item.get("matched_topics", [])

        # Техническая диагностика нужна только разработчику.
        # В переменную post и реальное Telegram-сообщение она не попадает.
        print(f"Темы: {', '.join(matched_topics)}")
        print()
        print(post)
        print()
        continue

    # Сейчас поддерживается режим: одна новость — один пост.
    if POST_MODE != "single":
        print(f"Ошибка: режим POST_MODE={POST_MODE!r} не поддерживается.")
        print()
        continue

    # Ошибка одного поста не должна останавливать следующие.
    if send_telegram_post(post):
        print("Пост успешно отправлен в Telegram.")

        # Только подтверждённая Telegram публикация
        # считается обработанной и попадает в историю.
        add_to_history(news_item, history)
        history_changed = True

    else:
        print("Пост не отправлен. История для этой новости не изменена.")

    print()

# Сохраняем накопленные успешные публикации одним вызовом.
if not DRY_RUN and history_changed:
    save_history(history)
