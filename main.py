from bs4 import FeatureNotFound
from bs4.exceptions import ParserRejectedMarkup
from requests import RequestException

from processing.deduplicator import remove_duplicates
from collectors.rss_collector import collect_rss
from config import (
    DRY_RUN,
    EXCLUDE_KEYWORDS,
    MAX_NEWS_PER_RUN,
    NEWS_LOOKBACK_DAYS,
    SCORE_RULES,
    SOURCES,
    TOPICS,
)
from processing.filters import (
    filter_by_date,
    filter_by_topics,
    sort_by_score,
)
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


# Здесь будем собирать новости со всех источников.
all_news = []

# Проходим по каждому источнику из config.py.
for source in SOURCES:
    # Пока обрабатываем только RSS-источники.
    if source["type"] == "rss":
        news_items = collect_rss(source)

        print(f"Источник: {source['name']}")
        print(f"Найдено новостей: {len(news_items)}")
        print()

        # Добавляем новости текущего источника
        # в общий список.
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


# Показываем первые 10 подходящих новостей.
for news_item in selected_news:
    post = generate_post(news_item)

    print("=" * 60)
    print(post)
    print()

# В обычном режиме считаем выбранные новости обработанными
# и сохраняем обновлённую историю на диск.
#
# В DRY_RUN этот блок целиком пропускается. Благодаря этому
# одни и те же новости можно проверять несколько раз подряд.
if not DRY_RUN:
    for news_item in selected_news:
        add_to_history(news_item, history)

    save_history(history)
