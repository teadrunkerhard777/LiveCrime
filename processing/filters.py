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


def filter_by_topics(news_items, topics, exclude_keywords):
    """
    Оставляет свежие криминальные новости по нужным темам
    и отбрасывает только явные посторонние совпадения.
    """

    filtered_news = []

    for news_item in news_items:
        title = news_item["title"].lower()
        description = news_item["description"].lower()

        full_text = f"{title} {description}"

        # Проверяем наличие хотя бы одной нужной темы.
        has_topic = any(
            topic.lower() in full_text
            for topic in topics
        )

        # Проверяем явные стоп-слова.
        has_excluded_keyword = any(
            keyword.lower() in full_text
            for keyword in exclude_keywords
        )

        # Оставляем новость, если она подходит по теме
        # и не относится к явно посторонней тематике.
        if has_topic and not has_excluded_keyword:
            filtered_news.append(news_item)

    return filtered_news


def calculate_score(news_item, score_rules):
    """
    Считает рейтинг интересности новости.

    Чем больше подходящих ключевых слов встречается
    в заголовке и описании, тем выше score.
    """

    title = news_item["title"].lower()
    description = news_item["description"].lower()

    full_text = f"{title} {description}"

    score = 0

    for keyword, points in score_rules.items():
        # Если ключевое слово встречается в тексте,
        # добавляем соответствующее количество баллов.
        if keyword.lower() in full_text:
            score += points

        # Совпадение в заголовке считаем более важным.
        if keyword.lower() in title:
            score += 1

    return score


def sort_by_score(news_items, score_rules):
    """
    Добавляет каждой новости рейтинг
    и сортирует список от наиболее интересных к менее интересным.
    """

    for news_item in news_items:
        news_item["score"] = calculate_score(
            news_item,
            score_rules,
        )

    return sorted(
        news_items,
        key=lambda item: item["score"],
        reverse=True,
    )
