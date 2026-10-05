import re
from datetime import datetime, timedelta, timezone


CONTEXTUAL_SCORE_BONUS_LIMIT = 3


# Явные метафоры со словом "убийца" не являются crime-событиями.
# Список намеренно узкий: реальные люди-убийцы должны продолжать проходить.
FIGURATIVE_HOMICIDE_PATTERNS = (
    r"\bубийц\w*\s+(?:иммунитет\w*|здоровь\w*|настроени\w*|сн\w*|продуктивност\w*)\b",
)

# Просьба об убийстве не подтверждает, что человек был убит.
# Маскируем только глагол внутри этой конструкции: отдельное сообщение
# о совершённом убийстве в той же новости должно сохранить свой сигнал.
REQUESTED_KILLING_PATTERN = (
    r"\b(?:просил(?:а|и)?|попросил(?:а|и)?|умолял(?:а|и)?)\b"
    r"[^.!?\n]{0,60}?\bчтобы\b[^.!?\n]{0,35}?"
    r"\b(?P<killing>убил(?:а|и)?|убит(?:а|о|ы)?)\b"
)


def _without_requested_killing(full_text):
    """Убирает ложный homicide-сигнал, сохраняя остальные слова текста."""

    def mask_killing(match):
        start = match.start("killing") - match.start()
        end = match.end("killing") - match.start()
        fragment = match.group()
        return fragment[:start] + " " * (end - start) + fragment[end:]

    return re.sub(
        REQUESTED_KILLING_PATTERN,
        mask_killing,
        full_text,
        flags=re.IGNORECASE,
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


# Новостной дайджест может вынести одно тяжёлое событие в заголовок,
# хотя сама страница объединяет несколько несвязанных материалов.
# Для отказа требуем несколько редакционных признаков, чтобы не блокировать
# обычную отдельную статью из-за одного случайного слова «новости».
NEWS_ROUNDUP_TITLE_PATTERNS = (
    r":\s*(?:главн\w+\s+)?новост\w+\s+\d{1,2}\s+[а-яё]+(?:\s+\d{4})?\b",
    r"\b(?:главн\w+|итог\w+)\s+(?:дн\w+|сут\w+)\b",
)
NEWS_ROUNDUP_BODY_PATTERNS = (
    r"\bчто произошло за сутки\b",
    r"\bсобрал\w+\s+главн\w+\s+в\s+этом\s+дайджест\w*\b",
    r"\bподводим\s+итоги\s+\d{1,2}\s+[а-яё]+\b",
)


# Реакция политика на гибель лидера — отдельный редакционный формат.
# Одного упоминания президента или Ирана недостаточно для отказа:
# нужны и комментарий в заголовке, и явная связь погибшего с должностью.
POLITICAL_COMMENTARY_PATTERN = (
    r"\b(?:раскрыл\w*\s+отношени\w*|рассказал\w*\s+об\s+отношени\w*|"
    r"выразил\w*\s+соболезнован\w*|почтил\w*\s+память|"
    r"осудил\w*\s+убийств\w*)\b"
)
POLITICAL_LEADER_PATTERN = (
    r"(?:лидер\w*|президент\w*|премьер\w*|глав\w*\s+государств\w*)"
)
POLITICAL_DEATH_PATTERNS = (
    rf"\b(?:убит\w*|погибш\w*)\b[^.!?\n]{{0,40}}\b{POLITICAL_LEADER_PATTERN}\b",
    rf"\bубийств\w*\b[^.!?\n]{{0,40}}\b{POLITICAL_LEADER_PATTERN}\b",
)


def _is_political_death_commentary(news_item):
    """Отличает комментарий о погибшем лидере от новости о преступлении."""

    title = str(news_item.get("title", "")).casefold()
    return bool(
        re.search(POLITICAL_COMMENTARY_PATTERN, title)
        and any(re.search(pattern, title) for pattern in POLITICAL_DEATH_PATTERNS)
    )


# Пословица в политической оценке не описывает конкретное убийство.
# Требуем одновременно речевой формат, политический контекст и формулу:
# фамилия политика или слово «убийца» сами по себе ничего не запрещают.
POLITICAL_HOMICIDE_RHETORIC_PATTERN = (
    r"\bубийц\w*\s+(?:всегда\s+)?возвраща\w*\s+"
    r"(?:на|к)\s+мест[оу]\s+преступлени\w*\b"
)
POLITICAL_EVALUATION_PATTERN = (
    r"\b(?:оценил\w*|назвал\w*|прокомментировал\w*|"
    r"отреагировал\w*|сравнил\w*)\b"
)
POLITICAL_CONTEXT_PATTERN = (
    r"\b(?:мид|дипломат\w*|канцлер\w*|президент\w*|министр\w*|"
    r"премьер\w*|политик\w*|визит\w*|делегаци\w*)\b"
)


def _is_political_homicide_rhetoric(news_item):
    """Отличает политическую пословицу об убийцах от конкретного crime."""

    title = str(news_item.get("title", "")).casefold()
    if not (
        re.search(POLITICAL_HOMICIDE_RHETORIC_PATTERN, title)
        and re.search(POLITICAL_EVALUATION_PATTERN, title)
    ):
        return False

    # Если помимо фигуры речи заголовок сообщает о настоящем hard-event,
    # не отбрасываем его из-за цитаты или должности комментатора.
    factual_title = re.sub(POLITICAL_HOMICIDE_RHETORIC_PATTERN, "", title)
    if re.search(r"\b(?:убийств\w*|изнасилован\w*)\b", factual_title) or any(
        re.search(pattern, factual_title)
        for pattern in COMPLETED_HARD_EVENT_PATTERNS
    ):
        return False

    context = "\n".join(
        str(news_item.get(field, ""))
        for field in ("title", "description", "article_text")
    ).casefold()
    return bool(re.search(POLITICAL_CONTEXT_PATTERN, context))


# Обобщение о большой группе людей в политическом интервью — не отдельный
# crime-case. Нужны и агрегатный заголовок, и явный формат заявления.
AGGREGATE_VIOLENCE_PATTERN = (
    r"(?:\b(?:почти|практически)\s+все\b|\bбольшинств\w*\b|"
    r"\b\d+\s*(?:процент\w*|%))"
    r"[^.!?\n]{0,140}\b(?:изнасил\w*|убийств\w*|убит(?!ь)\w*)\b"
)
POLITICAL_SPEAKER_PATTERN = (
    r"\b(?:министр\w*|политик\w*|депутат\w*|канцлер\w*|президент\w*)\b"
)
REPORTED_STATEMENT_PATTERN = (
    r"\b(?:заявил\w*|рассказал\w*|сообщил\w*|интервью|подкаст\w*)\b"
)
CONCRETE_CASE_HEADLINE_PATTERN = (
    r"\b(?:по\s+делу|в\s+деле|задержан\w*|задержали|арестован\w*|"
    r"подозреваем\w*|заложниц\w*)\b"
)


def _is_aggregate_political_violence_statement(news_item):
    """Распознаёт политическое заявление о распространённости насилия."""

    title = str(news_item.get("title", "")).casefold()
    if not re.search(AGGREGATE_VIOLENCE_PATTERN, title):
        return False
    # Определённое дело/группа заложниц не становится статистикой из-за
    # слов «почти все». Обычные case-новости сохраняют прежние проверки.
    if re.search(CONCRETE_CASE_HEADLINE_PATTERN, title):
        return False

    # Смотрим начало материала, а не случайную политическую цитату внизу.
    # Если RSS пустой, та же проверка повторится после загрузки article_text.
    lead = (
        news_item.get("article_text") or news_item.get("description", "")
    )
    context = f"{title}\n{str(lead)[:800]}".casefold()
    return bool(
        re.search(POLITICAL_SPEAKER_PATTERN, context)
        and re.search(REPORTED_STATEMENT_PATTERN, context)
    )


# Дипломатический протест — реакция на crime, а не новый тяжёлый эпизод.
# Не запрещаем МИД/послов глобально: нужны действие и связь с преступлением.
DIPLOMATIC_REACTION_PATTERN = (
    r"\b(?:выразил\w*|заявил\w*)\b[^.!?\n]{0,80}\bпротест\w*\b|"
    r"\bвызвал\w*\b[^.!?\n]{0,50}\b(?:посла|послов)\b"
)
DIPLOMATIC_CONTEXT_PATTERN = (
    r"\b(?:мид|дипломат\w*|посол|посла|послу|послом|послы|послов|"
    r"министр\w*\s+иностранных\s+дел)\b"
)
DIPLOMATIC_CRIME_LINK_PATTERN = (
    r"\b(?:из-за|в\s+связи\s+с|после|по\s+поводу)\b"
    r"[^.!?\n]{0,80}\b(?:убийств\w*|изнасилован\w*|застрел\w*)\b"
)
DIPLOMATIC_LEAD_CONDEMNATION_PATTERN = (
    r"\b(?:премьер(?:-министр)?|мид|дипломат\w*|президент\w*|"
    r"министр\w*\s+иностранных\s+дел)\b"
    r"[^.!?\n]{0,160}\bосудил\w*\b[^.!?\n]{0,80}"
    r"\b(?:убийств\w*|изнасилован\w*|застрел\w*)\b"
)


def _is_diplomatic_crime_reaction(news_item):
    """Находит дипломатический повод с убийством только как причиной реакции."""

    title = str(news_item.get("title", "")).casefold()
    reaction = re.search(DIPLOMATIC_REACTION_PATTERN, title)
    if reaction is None or not re.search(DIPLOMATIC_CRIME_LINK_PATTERN, title):
        # Сенсационный заголовок может не назвать crime вовсе, а lead
        # сразу сообщает лишь о реакции премьера/дипломата на чужое дело.
        # Сохраняем прямой hard-заголовок: политическая цитата в теле статьи
        # не должна отменить новость о самом убийстве или задержании.
        if re.search(
            r"\b(?:убий\w*|изнасил\w*|застрел\w*|расстрел\w*|"
            r"убил(?:а|и)?|убит(?!ь)\w*|суицид\w*|самоубий\w*)\b",
            title,
        ):
            return False
        body = str(
            news_item.get("article_text") or news_item.get("description", "")
        ).strip()
        # Только первый абзац (до 600 символов), не поздние комментарии.
        lead = re.split(r"\n\s*\n", body, maxsplit=1)[0][:600].casefold()
        return bool(re.search(DIPLOMATIC_LEAD_CONDEMNATION_PATTERN, lead))

    # Если сначала сообщается само завершённое тяжёлое событие, сохраняем
    # новость: «Морпех убил женщину; МИД выразил протест из-за убийства».
    if any(
        re.search(pattern, title[:reaction.start()])
        for pattern in COMPLETED_HARD_EVENT_PATTERNS
    ):
        return False

    context = "\n".join(
        str(news_item.get(field, ""))
        for field in ("title", "description", "article_text")
    ).casefold()
    return bool(re.search(DIPLOMATIC_CONTEXT_PATTERN, context))


# Убийство в статусе разыскиваемого — предыстория, а не исход погони.
# Это узкое правило формата новости, а не запрет на задержания убийц.
SUSPECT_BACKGROUND_PATTERN = (
    r"\b(?:подозреваем\w*|обвиняем\w*|разыскиваем\w*)\s+"
    r"(?:в|за)\s+(?:совершени\w*\s+)?(?:убийств\w*|изнасилован\w*)\b"
)
NONFATAL_INCIDENT_PATTERN = (
    r"\b(?:ранил\w*|ранен\w*|погон\w*|перестрел\w*|авари\w*)\b"
)
FATAL_INCIDENT_PATTERN = (
    r"\b(?:погиб\w*|скончал\w*|умер(?:ла|ли)?|смертельн\w*|"
    r"убил(?:а|и)?|убит(?!ь)(?:а|о|ы)?|застрелил(?:а|и)?|"
    r"застрелян(?:а|о|ы)?)\b"
)


def _is_nonfatal_suspect_incident(news_item):
    """Отличает ранение/погоню от hard-события, упомянутого для розыска."""

    title = str(news_item.get("title", "")).casefold()
    if not re.search(SUSPECT_BACKGROUND_PATTERN, title):
        return False
    if not re.search(NONFATAL_INCIDENT_PATTERN, title):
        return False

    # Отдельное завершённое убийство в заголовке остаётся допустимым.
    current_title = re.sub(SUSPECT_BACKGROUND_PATTERN, "", title)
    if re.search(FATAL_INCIDENT_PATTERN, current_title):
        return False

    # Проверяем загруженное тело до отбора/публикации. Номинальное
    # «расследование убийства» не подтверждает смерть в текущей погоне.
    body = str(news_item.get("article_text") or news_item.get("description", ""))
    for sentence in re.split(r"[.!?\n]+", body.casefold()):
        if re.search(r"\b(?:ранее|до этого)\b", sentence):
            continue
        current_incident = re.search(
            r"\b(?:погон\w*|перестрел\w*|полицей\w*|при задержани\w*|"
            r"авари\w*|больниц\w*)\b", sentence
        )
        # Нужна связь смертельного исхода именно с текущим происшествием.
        if current_incident and re.search(FATAL_INCIDENT_PATTERN, sentence):
            return False

    return True


def _topic_matches(full_text, topic):
    """Ищет тематическую основу только с начала отдельного слова."""

    # Одну и ту же контекстную проверку используют фильтр и score.
    if topic.casefold() in {"убил", "убит"}:
        full_text = _without_requested_killing(full_text)

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
    factual_text = _without_requested_killing(full_text)
    has_completed_event = any(
        re.search(pattern, factual_text, re.IGNORECASE)
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


def _contains_news_roundup(news_item):
    """Находит много-сюжетный новостной дайджест, а не одно crime-событие."""

    title = str(news_item.get("title", "")).casefold()
    body = " ".join(
        str(news_item.get(field, ""))
        for field in ("description", "article_text")
    ).casefold()

    title_signals = sum(
        bool(re.search(pattern, title, re.IGNORECASE))
        for pattern in NEWS_ROUNDUP_TITLE_PATTERNS
    )
    body_signals = sum(
        bool(re.search(pattern, body, re.IGNORECASE))
        for pattern in NEWS_ROUNDUP_BODY_PATTERNS
    )

    # Заголовок дайджеста подтверждаем содержимым страницы. Если заголовок
    # нейтральный, двух независимых body-маркеров всё равно достаточно.
    return bool((title_signals and body_signals) or body_signals >= 2)


def _explicit_old_event_year(full_text, published_at, max_age_days):
    """Возвращает год, только если старый год явно относится к hard-event."""

    if published_at is None:
        return None

    event_year_patterns = (
        # Год старой судимости может стоять перед названием преступления:
        # «В 2015 году его признали виновным в изнасиловании». Новый штраф
        # за регистрацию не делает это тяжёлое преступление свежим.
        rf"\bв\s+((?:19|20)\d{{2}})\s+год[уа]\b[^.!?\n]{{0,60}}\b(?:признал\w*\s+виновн\w*|(?:был\w*\s+)?осужд[её]н\w*|осудил\w*)\s+(?:в|за)\s+(?:совершени\w*\s+)?{HARD_EVENT_WORD_PATTERN}\b",
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
    """Исключает дайджесты, animal events, покушения и старые события."""

    filtered_news = []

    for news_item in news_items:
        # После article loading все признаки читаются из того же news_item.
        # Граница полей не позволяет связать слово из заголовка с чужой
        # датой (например годом рождения) в первом абзаце статьи.
        full_text = "\n".join(
            str(news_item.get(field, ""))
            for field in ("title", "description", "article_text")
        ).casefold()

        rejection = None
        if _is_political_death_commentary(news_item):
            rejection = "political_commentary"
            reason = "political commentary about a deceased leader"
        elif _is_political_homicide_rhetoric(news_item):
            rejection = "political_rhetoric"
            reason = "political homicide rhetoric is not a concrete hard event"
        elif _is_diplomatic_crime_reaction(news_item):
            rejection = "diplomatic_reaction"
            reason = "diplomatic reaction; hard crime is background, not the news event"
        elif _is_aggregate_political_violence_statement(news_item):
            rejection = "aggregate_political_statement"
            reason = "aggregate political violence statement, not a concrete crime case"
        elif _contains_news_roundup(news_item):
            rejection = "news_roundup"
            reason = "multi-story news roundup is not one true-crime event"
        elif _is_nonfatal_suspect_incident(news_item):
            rejection = "nonfatal_suspect_incident"
            reason = "nonfatal suspect incident; hard crime is search background"
        elif _contains_animal_event(full_text):
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
        has_political_commentary = _is_political_death_commentary(news_item)
        has_political_rhetoric = _is_political_homicide_rhetoric(news_item)
        has_diplomatic_reaction = _is_diplomatic_crime_reaction(news_item)
        has_aggregate_statement = _is_aggregate_political_violence_statement(news_item)

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

        # В диагностике видно, какое совпадение отброшено как просьба.
        news_item["ignored_homicide_fragments"] = [
            match.group()
            for match in re.finditer(
                REQUESTED_KILLING_PATTERN, full_text, re.IGNORECASE
            )
        ]

        if matched_strong_topics:
            news_item["admission_reason"] = (
                f'hard serious topic "{matched_strong_topics[0]}"'
            )
        elif has_severe_conditional_event:
            news_item["admission_reason"] = (
                f'conditional "{matched_conditional_topics[0]}" + '
                f'severe outcome "{matched_serious_outcomes[0]}"'
            )

        if has_political_commentary:
            news_item["rejection_reason"] = (
                "political commentary about a deceased leader"
            )
        elif has_political_rhetoric:
            news_item["rejection_reason"] = (
                "political homicide rhetoric is not a concrete hard event"
            )
        elif has_diplomatic_reaction:
            news_item["rejection_reason"] = (
                "diplomatic reaction; hard crime is background, not the news event"
            )
        elif has_aggregate_statement:
            news_item["rejection_reason"] = (
                "aggregate political violence statement, not a concrete crime case"
            )
        elif not has_supported_topic and news_item["ignored_homicide_fragments"]:
            news_item["rejection_reason"] = (
                "requested killing is not a completed homicide"
            )
        elif has_figurative_homicide:
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
            and not has_political_commentary
            and not has_political_rhetoric
            and not has_diplomatic_reaction
            and not has_aggregate_statement
        )

        # Никакой score не может заменить hard serious допуск.
        if (
            matched_topics
            and has_supported_topic
            and not has_excluded_keyword
            and not has_figurative_homicide
            and not has_political_commentary
            and not has_political_rhetoric
            and not has_diplomatic_reaction
            and not has_aggregate_statement
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
