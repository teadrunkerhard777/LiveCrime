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

from storage.history import (
    add_to_history,
    is_published,
    load_history,
    save_history,
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

# Здесь будут только те новости,
# которых ещё нет в истории.
new_news = []

for news_item in unique_news:
    if not is_published(news_item, history):
        new_news.append(news_item)

# Для теста сохраняем первые 10 новых новостей в историю.
for news_item in new_news[:10]:
    add_to_history(news_item, history)

save_history(history)


print(f"Всего собрано новостей: {len(all_news)}")
print(
    f"За последние {NEWS_LOOKBACK_DAYS} дня: "
    f"{len(fresh_news)}"
)
print(f"Подходят по тематике: {len(topic_news)}")
print(f"После удаления дублей: {len(unique_news)}")
print(f"Новых новостей: {len(new_news)}")
print()


# Показываем первые 10 подходящих новостей.
for news_item in new_news[:10]:
    print(f"[score: {news_item['score']}]")
    print(news_item["title"])
    print(f"Дата: {news_item['published_at']}")
    print(news_item["url"])
    print()
