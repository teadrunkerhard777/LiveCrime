import re
from datetime import datetime, timedelta, timezone


CONTEXTUAL_SCORE_BONUS_LIMIT = 3


# Явные метафоры со словом "убийца" не являются crime-событиями.
# Список намеренно узкий: реальные люди-убийцы должны продолжать проходить.
FIGURATIVE_HOMICIDE_PATTERNS = (
    r"\bубийц\w*\s+(?:иммунитет\w*|здоровь\w*|настроени\w*|сн\w*|продуктивност\w*)\b",
)


# Эти формулировки явно описывают незавершённое преступление.
# Одно слово "покушение" не блокируем: рядом может быть завершённое убийство.
ATTEMPT_PATTERNS = (
    r"\bпокуш\w*\s+(?:на\s+)?(?:совершени\w*\s+)?(?:убийств\w*|изнасилован\w*|насильственн\w+\s+действ\w+\s+сексуальн\w+\s+характер\w*)",
    r"\bпопыт\w*\s+(?:совершени\w*\s+)?(?:убийств\w*|изнасилован\w*|насильственн\w+\s+действ\w+\s+сексуальн\w+\s+характер\w*)",
    r"\bпытал(?:ся|ась|ись)\s+(?:совершить\s+)?(?:убить|изнасиловать)",
    r"\b(?:обвиня\w*|осужд\w*|приговор\w*|предъяв\w*\s+обвинен\w*)[^.!?\n]{0,40}\bпокуш\w*",
    r"\bч\.?\s*3\s+ст\.?\s*30\s+ук\s+рф\b",
)

# Завершённое hard-событие сохраняет материал, даже если рядом описано
# покушение на ещё одного потерпевшего.
COMPLETED_HARD_EVENT_PATTERNS = (
    r"\bубил(?:а|и)?\b",
    r"\bубит(?!ь)(?:а|о|ы)?\b",
    r"\bизнасиловал(?:а|и)?\b",
    r"\bизнасилован(?:а|о|ы)?\b",
    r"\b(?:за|рас)стрелил(?:а|и)?\b",
    r"\b(?:за|рас)стрелян(?:а|о|ы)?\b",
    r"\b(?:совершил\w*|произошл\w*|раскрыл\w*|расследу\w*)[^.!?\n]{0,40}\b(?:убийств\w*|изнасилован\w*)\b",
    r"\b(?:самоубий\w*|суицид\w*|покончил(?:а)?\s+с\s+собой)\b",
    r"\b(?:нападен\w*|стрельб\w*|избиен\w*|избит\w*)[^.!?\n]{0,100}\b(?:погиб\w*|скончал\w*|умер(?:ла|ли)?|до\s+смерти)\b",
    r"\b(?:погиб\w*|скончал\w*|умер(?:ла|ли)?)\b[^.!?\n]{0,100}\b(?:нападен\w*|стрельб\w*|избиен\w*|избит\w*)\b",
)

HARD_EVENT_WORD_PATTERN = (
    r"(?:убийств\w*|изнасилован\w*|самоубийств\w*|суицид\w*|"
    r"застрел\w*|расстрел\w*|преступлен\w*)"
)

# Животные могут быть участниками происшествия, но это не true crime.
# Проверяем только явную связь животного с убийством, ранением или гибелью,
# а не запрещаем любое случайное упоминание животного в статье.
ANIMAL_PATTERN = (
    r"(?:медвед\w*|волк\w*|собак\w*|тигр\w*|леопард\w*|"
    r"кабан\w*|звер\w*|животн\w*|хищник\w*)"
)
ANIMAL_OBJECT_MODIFIER_PATTERN = (
    r"(?:(?:одн\w*|дв\w*|тр\w*|четыр\w*|пят\w*|шест\w*|"
    r"дик\w*|бур\w*|бездомн\w*|опасн\w*|агрессивн\w*)\s+){0,2}"
)
ANIMAL_EVENT_PATTERNS = (
    # Животное прямо убило человека или смертельно напало на него.
    rf"\b{ANIMAL_PATTERN}\b[^.!?\n]{{0,80}}\b(?:убил\w*|загрыз\w*|растерзал\w*|смертельно\s+напал\w*)\b",
    rf"\b(?:нападен\w*|атак\w*)\s+{ANIMAL_PATTERN}\b[^.!?\n]{{0,100}}\b(?:погиб\w*|скончал\w*|умер\w*)\b",
    rf"\b(?:погиб\w*|гибел\w*|скончал\w*|умер\w*)[^.!?\n]{{0,80}}\b(?:от\s+)?(?:нападен\w*\s+)?{ANIMAL_PATTERN}\b",
    # Человек убил животное: сильный глагол не должен имитировать homicide.
    rf"\b(?:убил\w*|застрелил\w*|расстрелял\w*)\s+{ANIMAL_OBJECT_MODIFIER_PATTERN}{ANIMAL_PATTERN}\b",
    rf"(?<!владельца\s)(?<!хозяина\s)\b{ANIMAL_PATTERN}\b\s+(?:были?\s+)?(?:убиты|застрелены|расстреляны|убили|застрелили|расстреляли)\b",
)

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


def _contains_standalone_attempt(full_text):
    """Отличает самостоятельное покушение от завершённого hard-события."""

    has_attempt = any(
        re.search(pattern, full_text, re.IGNORECASE)
        for pattern in ATTEMPT_PATTERNS
    )
    has_completed_event = any(
        re.search(pattern, full_text, re.IGNORECASE)
        for pattern in COMPLETED_HARD_EVENT_PATTERNS
    )
    return has_attempt and not has_completed_event


def _contains_animal_event(full_text):
    """Находит явное насилие между человеком и животным."""

    return any(
        re.search(pattern, full_text, re.IGNORECASE)
        for pattern in ANIMAL_EVENT_PATTERNS
    )


def _contains_nonfatal_rasstrel(full_text):
    """Не считает форму «расстрелял» убийством без смертельного исхода."""

    has_rasstrel = re.search(
        r"\bрасстрелял\w*\b",
        full_text,
        re.IGNORECASE,
    )
    has_fatal_outcome = re.search(
        r"\b(?:убил\w*|убит(?!ь)\w*|погиб\w*|скончал\w*|умер\w*|"
        r"смертельн\w*|до\s+смерти)\b",
        full_text,
        re.IGNORECASE,
    )
    return bool(has_rasstrel and not has_fatal_outcome)


def _explicit_old_event_year(full_text, published_at, max_age_days):
    """Возвращает год, только если старый год явно относится к hard-event."""

    if published_at is None:
        return None

    event_year_patterns = (
        rf"\b{HARD_EVENT_WORD_PATTERN}[^.!?\n]{{0,100}}\b((?:19|20)\d{{2}})\s+год",
        rf"\b(?:дел\w*\s+(?:об?|по)|раскрыл\w*|расследу\w*)[^.!?\n]{{0,60}}\b{HARD_EVENT_WORD_PATTERN}[^.!?\n]{{0,50}}\b((?:19|20)\d{{2}})\s+год",
        rf"\b(?:убил\w*|изнасиловал\w*)[^.!?\n]{{0,100}}\b((?:19|20)\d{{2}})\s+год",
        rf"\bпреступлен\w*[^.!?\n]{{0,50}}\b(?:совершен\w*|произошл\w*)[^.!?\n]{{0,40}}\b((?:19|20)\d{{2}})\s+год",
        # В ряде статей дата стоит раньше описания смертельного исхода:
        # "в июне 2024 года ... трое детей утонули".
        r"\b(?:в\s+)?(?:январ\w*|феврал\w*|март\w*|апрел\w*|ма[ея]|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s+((?:19|20)\d{2})\s+год\w*[^.!?\n]{0,180}\b(?:убил\w*|изнасиловал\w*|утонул\w*|погиб\w*|скончал\w*|умер\w*|сбросил\w*)\b",
        r"\b(?:инцидент\w*|происшестви\w*|нападен\w*|стрельб\w*)\s+(?:произош\w*|случил\w*)[^.!?\n]{0,50}\b(?:в\s+)?(?:январ\w*|феврал\w*|март\w*|апрел\w*|ма[ея]|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s+((?:19|20)\d{2})\s+год",
    )

    for pattern in event_year_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if not match:
            continue

        event_year = int(match.group(1))

        # В полицейских сводках после события часто указывают год рождения:
        # "убийство мужчины, 1978 года рождения". Это не дата преступления.
        year_context = full_text[
            match.start(1):match.end(1) + 30
        ]
        if re.match(
            rf"{event_year}\s+года\s+рождени\w*",
            year_context,
            re.IGNORECASE,
        ):
            continue

        # Для одного года берём самый поздний возможный день. Так материал
        # отклоняется лишь тогда, когда событие точно старше порога.
        latest_possible_event = datetime(
            event_year, 12, 31, tzinfo=published_at.tzinfo or timezone.utc
        )
        if published_at - latest_possible_event > timedelta(days=max_age_days):
            return event_year

    return None


def _has_explicit_old_event_age(full_text, max_age_days):
    """Распознаёт явную многолетнюю давность рядом с преступлением."""

    age_patterns = (
        rf"\b{HARD_EVENT_WORD_PATTERN}[^.!?\n]{{0,80}}\b(\d{{1,3}})(?:[- ]?летн\w*\s+давност\w*|\s+лет\s+назад|\s+год\w*\s+назад|\s+год\w*\s+давност\w*)",
        rf"\bспустя\s+(\d{{1,3}})\s+(?:лет|год\w*)[^.!?\n]{{0,60}}\b{HARD_EVENT_WORD_PATTERN}",
    )
    minimum_old_years = max_age_days / 365

    for pattern in age_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match and int(match.group(1)) > minimum_old_years:
            return int(match.group(1))

    # Частая редакционная форма без цифр: "убийство двадцатилетней давности".
    word_age_pattern = (
        rf"\b{HARD_EVENT_WORD_PATTERN}[^.!?\n]{{0,80}}\b"
        r"(?:десяти|двадцати|тридцати|сорока|пятидесяти)летн\w*\s+давност\w*"
    )
    if re.search(word_age_pattern, full_text, re.IGNORECASE):
        return "many"

    return None


def filter_by_event_policy(news_items, max_event_age_days):
    """Исключает animal events, покушения и явно старые hard-события."""

    filtered_news = []

    for news_item in news_items:
        # После article loading все признаки читаются из того же news_item.
        full_text = " ".join(
            str(news_item.get(field, ""))
            for field in ("title", "description", "article_text")
        ).casefold()

        rejection = None
        if _contains_animal_event(full_text):
            rejection = "animal_event"
            reason = "animal violence is not a human true-crime event"
        elif _contains_nonfatal_rasstrel(full_text):
            rejection = "nonfatal_shooting"
            reason = "shooting without an explicit fatal outcome"
        elif _contains_standalone_attempt(full_text):
            rejection = "standalone_attempt"
            reason = "attempt without a completed hard event"
        else:
            old_year = _explicit_old_event_year(
                full_text,
                news_item.get("published_at"),
                max_event_age_days,
            )
            old_age = _has_explicit_old_event_age(
                full_text,
                max_event_age_days,
            )
            if old_year is not None:
                rejection = "stale_event"
                reason = f"hard event explicitly tied to year {old_year}"
            elif old_age is not None:
                rejection = "stale_event"
                reason = f"hard event explicitly described as {old_age} years old"

        news_item["event_policy_passed"] = rejection is None
        news_item["event_policy_rejection"] = rejection

        if rejection is None:
            filtered_news.append(news_item)
        else:
            news_item["rejection_reason"] = reason

    return filtered_news


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
        has_figurative_homicide = any(
            re.search(pattern, full_text, re.IGNORECASE)
            for pattern in FIGURATIVE_HOMICIDE_PATTERNS
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

        if has_figurative_homicide:
            news_item["rejection_reason"] = "figurative homicide language"
        elif has_excluded_keyword:
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
            and not has_figurative_homicide
        )

        # Никакой score не может заменить hard serious допуск.
        if (
            matched_topics
            and has_supported_topic
            and not has_excluded_keyword
            and not has_figurative_homicide
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
