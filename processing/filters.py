import re
from datetime import datetime, timedelta, timezone


def _topic_matches(full_text, topic):
    """Ищет тематическую основу только с начала отдельного слова."""

    # Левая граница не даёт "следств" совпасть внутри "последствия".
    pattern = rf"(?<!\w){re.escape(topic.casefold())}"
    return re.search(pattern, full_text) is not None


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


def filter_by_topics(
    news_items,
    topics,
    exclude_keywords,
    crime_context_keywords=(),
    strong_topics=None,
    contextual_topics=None,
):
    """
    Оставляет свежие криминальные новости по нужным темам
    и отбрасывает только явные посторонние совпадения.
    """

    filtered_news = []
    strong_topic_set = {
        topic.casefold() for topic in (strong_topics or topics)
    }
    contextual_topic_set = {
        topic.casefold() for topic in (contextual_topics or ())
    }

    for news_item in news_items:
        title = news_item["title"].casefold()
        description = news_item["description"].casefold()

        full_text = f"{title} {description}"

        # Сохраняем все совпавшие основы, а не только первое совпадение.
        # Это объясняет, почему конкретная новость прошла фильтр.
        matched_topics = [
            topic
            for topic in topics
            if _topic_matches(full_text, topic)
        ]

        # Проверяем явные стоп-слова.
        has_excluded_keyword = any(
            keyword.casefold() in full_text
            for keyword in exclude_keywords
        )

        # Разделение сохраняем в news_item для понятной диагностики.
        matched_strong_topics = [
            topic for topic in matched_topics
            if topic.casefold() in strong_topic_set
        ]
        matched_contextual_topics = [
            topic for topic in matched_topics
            if topic.casefold() in contextual_topic_set
        ]

        # Неоднозначную тему подтверждаем явной уголовной конструкцией.
        matched_crime_contexts = [
            keyword for keyword in crime_context_keywords
            if keyword.casefold() in full_text
        ]

        # Сильная тема достаточна сама по себе. Слабая требует явной
        # уголовной конструкции и позже ещё проходит minimum score.
        has_supported_topic = bool(matched_strong_topics) or (
            bool(matched_contextual_topics) and bool(matched_crime_contexts)
        )

        # Диагностика хранится в том же news_item и не рассинхронизируется.
        news_item["matched_topics"] = matched_topics
        news_item["strong_topics"] = matched_strong_topics
        news_item["contextual_topics"] = matched_contextual_topics

        if matched_strong_topics and matched_contextual_topics:
            news_item["admission_reason"] = (
                f'contextual "{matched_contextual_topics[0]}" + '
                f'strong "{matched_strong_topics[0]}"'
            )
        elif matched_strong_topics:
            news_item["admission_reason"] = (
                f'strong topic "{matched_strong_topics[0]}"'
            )
        elif matched_contextual_topics and matched_crime_contexts:
            news_item["admission_reason"] = (
                f'contextual "{matched_contextual_topics[0]}" + '
                f'explicit context "{matched_crime_contexts[0]}"'
            )

        if has_excluded_keyword:
            news_item["rejection_reason"] = "excluded keyword"
        elif matched_contextual_topics and not matched_crime_contexts:
            topics_text = ", ".join(matched_contextual_topics)
            news_item["rejection_reason"] = (
                f"only weak topic: {topics_text}"
            )
        elif not matched_topics:
            news_item["rejection_reason"] = "no crime topics"
        elif not has_supported_topic:
            news_item["rejection_reason"] = "no supporting crime context"

        news_item["strict_filter_passed"] = bool(
            matched_topics
            and has_supported_topic
            and not has_excluded_keyword
        )

        # Оставляем новость, если она подходит по теме
        # и неоднозначные основы подтверждены криминальным контекстом.
        if (
            matched_topics
            and has_supported_topic
            and not has_excluded_keyword
        ):
            filtered_news.append(news_item)

    return filtered_news


def calculate_score(news_item, score_rules):
    """
    Считает рейтинг интересности новости.

    Чем больше подходящих ключевых слов встречается
    в заголовке и описании, тем выше score.
    """

    title = news_item["title"].casefold()
    description = news_item["description"].casefold()

    full_text = f"{title} {description}"

    score = 0

    for keyword, points in score_rules.items():
        # Используем ту же границу слова, что и strict filter.
        if _topic_matches(full_text, keyword):
            score += points

    return score


def add_scores(news_items, score_rules):
    """Сохраняет score в каждом news_item без изменения порядка."""

    for news_item in news_items:
        news_item["score"] = calculate_score(news_item, score_rules)

    return news_items


def filter_by_minimum_score(news_items, minimum_score):
    """Оставляет только достаточно значимые true crime материалы."""

    publication_news = []

    for news_item in news_items:
        if news_item.get("score", 0) >= minimum_score:
            publication_news.append(news_item)
        else:
            news_item["rejection_reason"] = (
                f'score {news_item.get("score", 0)} below minimum '
                f"{minimum_score}"
            )

    return publication_news


def sort_by_score(news_items, score_rules):
    """
    Добавляет каждой новости рейтинг
    и сортирует список от наиболее интересных к менее интересным.
    """

    add_scores(news_items, score_rules)

    # sorted() стабилен: при равном score сохраняется исходный порядок RSS.
    return sorted(
        news_items,
        key=lambda item: item["score"],
        reverse=True,
    )
