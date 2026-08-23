from config import NEWS_LOOKBACK_DAYS, SOURCES
from collectors.rss_collector import collect_rss
from processing.filters import filter_by_date
from config import NEWS_LOOKBACK_DAYS, SOURCES, TOPICS
from processing.filters import filter_by_date, filter_by_topics

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
# которые подходят по тематике канала.
topic_news = filter_by_topics(
    fresh_news,
    TOPICS,
)

print(f"Всего собрано новостей: {len(all_news)}")
print(
    f"За последние {NEWS_LOOKBACK_DAYS} дня: "
    f"{len(fresh_news)}"
)
print(f"Подходят по тематике: {len(topic_news)}")
print()


# Пока показываем первые 5 новостей
# из общего списка.
# Показываем первые 5 новостей
# вместе с датой публикации.
for news_item in topic_news[:5]:
    print(news_item["title"])
    print(f"Дата: {news_item['published_at']}")
    print(news_item["url"])
    print()
