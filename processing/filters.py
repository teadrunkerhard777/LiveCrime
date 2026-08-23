from datetime import datetime, timedelta, timezone


def filter_by_date(news_items, lookback_days):
    """
    Оставляет только новости за последние N дней.
    """

    # Текущее время в UTC.
    now = datetime.now(timezone.utc)

    # Самая ранняя допустимая дата публикации.
    cutoff_date = now - timedelta(days=lookback_days)

    fresh_news = []

    for news_item in news_items:
        published_at = news_item["published_at"]

        # Если у новости нет корректной даты,
        # пока просто пропускаем её.
        if published_at is None:
            continue

        # Оставляем только свежие публикации.
        if published_at >= cutoff_date:
            fresh_news.append(news_item)

    return fresh_news


def filter_by_topics(news_items, topics):
    """
    Оставляет только новости, в которых встречается
    хотя бы одна тема из списка TOPICS.
    """

    filtered_news = []

    for news_item in news_items:
        # Ищем тему и в заголовке, и в описании.
        text = (
            f"{news_item['title']} "
            f"{news_item['description']}"
        ).lower()

        # Если найдено хотя бы одно совпадение,
        # новость проходит фильтр.
        if any(topic.lower() in text for topic in topics):
            filtered_news.append(news_item)

    return filtered_news


def filter_by_topics(news_items, topics):
    """
    Оставляет только новости, в которых встречается
    хотя бы одна из интересующих нас тематик.
    """

    filtered_news = []

    for news_item in news_items:
        # Объединяем заголовок и описание,
        # чтобы искать тему сразу в обоих полях.
        text = (
            f"{news_item['title']} "
            f"{news_item['description']}"
        ).lower()

        # Проверяем, есть ли хотя бы одна тема в тексте.
        if any(topic.lower() in text for topic in topics):
            filtered_news.append(news_item)

    return filtered_news
