from processing.deduplicator import remove_duplicates
from collectors.rss_collector import collect_rss
from config import (
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


# ====================НОВЫЕ=======================


# Здесь будут только те новости,
# которых ещё нет в истории.
new_news = []

for news_item in unique_news:
    if not is_published(news_item, history):
        new_news.append(news_item)


# Ограничиваем количество новостей,
# которые попадут в текущую подборку.
selected_news = new_news[:MAX_NEWS_PER_RUN]

if selected_news:
    fetch_article_html(selected_news[0]["url"])

    # Временно проверяем извлечение текста
# только на первой выбранной новости.
if selected_news:
    test_news = selected_news[0]

    html = fetch_article_html(test_news["url"])
    article_text = extract_article_text(html)

    print("=" * 60)
    print("ТЕСТ ТЕКСТА СТАТЬИ")
    print()
    print(article_text[:3000])
    print()

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

    # Пока считаем выбранную новость обработанной.
    add_to_history(news_item, history)

save_history(history)
