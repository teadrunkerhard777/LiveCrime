import re
from datetime import datetime, timedelta, timezone


CONTEXTUAL_SCORE_BONUS_LIMIT = 3


def _topic_matches(full_text, topic):
    """Ищет тематическую основу только с начала отдельного слова."""

    # Левая граница не даёт "следств" совпасть внутри "последствия".
    suffix_guard = ""

    # "убит" покрывает "убит/убита/убиты", но не инфинитив "убить".
    # Иначе фраза "пытался убить" ошибочно превращала бы покушение в убийство.
    if topic.casefold() == "убит":
        suffix_guard = r"(?!ь)"

    pattern = rf"(?<!\w){re.escape(topic.casefold())}{suffix_guard}"
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
    serious_outcome_keywords=(),
    strong_topics=None,
    contextual_topics=None,
    conditional_serious_topics=(),
):
    """
    Оставляет только hard true crime материалы.

    Contextual topics не могут открыть фильтр без прямой тяжёлой темы
    или сочетания насильственного действия с тяжёлым исходом.
    """

    filtered_news = []
    strong_topic_set = {
        topic.casefold() for topic in (strong_topics or topics)
    }
    contextual_topic_set = {
        topic.casefold() for topic in (contextual_topics or ())
    }
    conditional_topic_set = {
        topic.casefold() for topic in conditional_serious_topics
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

        # Тяжёлый исход учитываем только рядом с условно-насильственной темой.
        matched_serious_outcomes = [
            keyword for keyword in serious_outcome_keywords
            if _topic_matches(full_text, keyword)
        ]
        matched_conditional_topics = [
            topic for topic in matched_contextual_topics
            if topic.casefold() in conditional_topic_set
        ]

        # Например, "избил" недостаточно, а "избил до смерти" проходит.
        has_severe_conditional_event = bool(
            matched_conditional_topics and matched_serious_outcomes
        )
        has_supported_topic = bool(matched_strong_topics) or (
            has_severe_conditional_event
        )

        serious_topics = matched_strong_topics.copy()

        if has_severe_conditional_event:
            serious_topics.append(
                f"{matched_conditional_topics[0]} + "
                f"{matched_serious_outcomes[0]}"
            )

        # Диагностика хранится в том же news_item и не рассинхронизируется.
        news_item["matched_topics"] = matched_topics
        news_item["strong_topics"] = serious_topics
        news_item["contextual_topics"] = matched_contextual_topics

        if matched_strong_topics:
            news_item["admission_reason"] = (
                f'hard serious topic "{matched_strong_topics[0]}"'
            )
        elif has_severe_conditional_event:
            news_item["admission_reason"] = (
                f'conditional "{matched_conditional_topics[0]}" + '
                f'severe outcome "{matched_serious_outcomes[0]}"'
            )

        if has_excluded_keyword:
            news_item["rejection_reason"] = "excluded keyword"
        elif matched_conditional_topics and not matched_serious_outcomes:
            topics_text = ", ".join(matched_conditional_topics)
            news_item["rejection_reason"] = (
                f"violent context without severe outcome: {topics_text}"
            )
        elif matched_contextual_topics:
            topics_text = ", ".join(matched_contextual_topics)
            news_item["rejection_reason"] = (
                f"only contextual topics: {topics_text}"
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

        # Никакой score не может заменить hard serious допуск.
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

    severity_score = 0
    contextual_bonus = 0

    for keyword, points in score_rules.items():
        # Используем ту же границу слова, что и strict filter.
        if _topic_matches(full_text, keyword):
            if points > 1:
                # Несколько форм одного тяжёлого события не удваивают severity.
                severity_score = max(severity_score, points)
            else:
                contextual_bonus += points

    # Длинное полицейское описание не должно выигрывать только числом
    # procedural-слов: общий contextual bonus намеренно ограничен.
    contextual_bonus = min(
        contextual_bonus,
        CONTEXTUAL_SCORE_BONUS_LIMIT,
    )

    return severity_score + contextual_bonus


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
