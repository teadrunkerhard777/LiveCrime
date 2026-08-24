from processing.deduplicator import remove_duplicates
from collectors.rss_collector import collect_rss
from config import (
    EXCLUDE_KEYWORDS,
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


print(f"Всего собрано новостей: {len(all_news)}")
print(
    f"За последние {NEWS_LOOKBACK_DAYS} дня: "
    f"{len(fresh_news)}"
)
print(f"Подходят по тематике: {len(topic_news)}")
print(f"После удаления дублей: {len(unique_news)}")
print()


# Показываем первые 10 подходящих новостей.
for news_item in unique_news[:10]:
    print(f"[score: {news_item['score']}]")
    print(news_item["title"])
    print(f"Дата: {news_item['published_at']}")
    print(news_item["url"])
    print()
