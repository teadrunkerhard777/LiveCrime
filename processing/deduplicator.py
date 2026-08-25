import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher


# Event comparison использует только начало статьи: там обычно находятся
# место, участники и основные обстоятельства события.
EVENT_TEXT_LIMIT = 1600
EVENT_TIME_WINDOW = timedelta(hours=36)
MIN_SHARED_EVENT_TOKENS = 5
MIN_EVENT_TOKEN_OVERLAP = 0.45
MIN_EVENT_TOKEN_JACCARD = 0.20

# Разные словоформы одной тяжёлой темы приводятся к общей категории.
# Например, "застрел" и "убий" относятся к одному homicide-событию.
EVENT_TOPIC_FAMILIES = {
    "homicide": (
        "убий",
        "убил",
        "убит",
        "застрел",
        "расстрел",
    ),
    "sexual_violence": ("изнасил",),
    "suicide": (
        "самоубий",
        "суицид",
        "покончил с собой",
        "покончила с собой",
    ),
}

# Частые процедурные слова не являются фактами конкретного события.
# Их совпадение не должно объединять разные уголовные дела.
EVENT_NOISE_PREFIXES = (
    "суд",
    "следств",
    "сообщ",
    "уголов",
    "дел",
    "приговор",
    "обвин",
    "задерж",
    "полиц",
    "правоохран",
    "мужчин",
    "женщин",
    "человек",
    "знаком",
    "произош",
    "результ",
    "получ",
    "пресс-служб",
    "стат",
    "регион",
    "информац",
    "пользовател",
    "электрон",
    "ресурс",
    "сайт",
    "cookies",
    "метрическ",
    "программ",
    "обработ",
    "хранен",
    "обновлен",
    "изменен",
    "обезличиван",
    "блокирован",
    "уничтожен",
    "персональн",
    "владельц",
    "политик",
    "соглас",
    "рекомендательн",
    "технолог",
)

EVENT_STOP_WORDS = {
    "был",
    "была",
    "были",
    "будет",
    "весь",
    "для",
    "его",
    "ему",
    "еще",
    "или",
    "как",
    "который",
    "между",
    "место",
    "один",
    "она",
    "они",
    "при",
    "свой",
    "также",
    "того",
    "этот",
    "года",
    "году",
}

# Суффиксы нужны только для лёгкой нормализации словоформ.
# Полноценный морфологический пакет для этой задачи не добавляется.
RUSSIAN_INFLECTION_SUFFIXES = tuple(sorted(
    (
        "иями", "ями", "ами", "ного", "нему", "ными", "ними",
        "ого", "ему", "ому", "ыми", "ими", "иях", "ах", "ях",
        "ной", "ная", "ную", "ние", "ния", "ний", "ией", "ие",
        "ые", "ий", "ый", "ой", "ая", "яя", "ое", "ее", "ов",
        "ев", "ам", "ям", "ом", "ем", "а", "я", "ы", "и", "у",
        "ю", "е", "о",
    ),
    key=len,
    reverse=True,
))

LOCATION_PATTERN = re.compile(
    r"(?<!\w)(?:[Вв]|[Пп]од|[Вв]озле|[Ии]з)\s+"
    r"(?:села\s+|города\s+|деревни\s+|района\s+|области\s+)?"
    r"([А-ЯЁ][а-яё-]{3,})"
)


def normalize_title(title):
    """Приводит заголовок к единому виду для сравнения."""

    normalized = title.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


def remove_duplicates(news_items, debug=False):
    """Последовательно удаляет URL, title и cross-source event дубли."""

    unique_news = []
    seen_urls = set()

    for news_item in news_items:
        url = news_item["url"]

        # Первый слой: точный дубль URL.
        if url in seen_urls:
            continue

        duplicate_index = None
        duplicate_details = None

        # Второй и третий слои: exact/similar title и event fingerprint.
        for index, unique_item in enumerate(unique_news):
            if titles_are_similar(
                news_item["title"],
                unique_item["title"],
            ):
                duplicate_index = index
                break

            details = compare_event_fingerprints(news_item, unique_item)

            if details["is_duplicate"]:
                duplicate_index = index
                duplicate_details = details
                break

        if duplicate_index is None:
            seen_urls.add(url)
            unique_news.append(news_item)
            continue

        if duplicate_details is None:
            continue

        existing_item = unique_news[duplicate_index]
        preferred_item = _choose_preferred_event_item(
            existing_item,
            news_item,
        )

        if debug:
            _print_event_duplicate(
                existing_item,
                news_item,
                duplicate_details,
                preferred_item,
            )

        # При равном score более полный article_text/image может заменить
        # уже оставленный материал. Порядок остальных новостей стабилен.
        if preferred_item is news_item:
            unique_news[duplicate_index] = news_item

        seen_urls.add(url)

    return unique_news


def titles_are_similar(title_1, title_2, threshold=0.75):
    """Проверяет старое сходство нормализованных заголовков."""

    if title_similarity(title_1, title_2) < threshold:
        return False

    # Очень похожие процессуальные заголовки о разных городах
    # относятся к разным делам и не должны сливаться.
    first_locations = _extract_location_tokens(title_1)
    second_locations = _extract_location_tokens(title_2)

    if (
        first_locations
        and second_locations
        and first_locations.isdisjoint(second_locations)
    ):
        return False

    return True


def title_similarity(title_1, title_2):
    """Возвращает фактический SequenceMatcher ratio заголовков."""

    first = normalize_title(title_1)
    second = normalize_title(title_2)
    return SequenceMatcher(None, first, second).ratio()


def build_event_fingerprint(news_item):
    """Создаёт компактный rule-based fingerprint события."""

    article_text = (
        news_item.get("article_text")
        or news_item.get("description", "")
    )
    event_text = (
        f"{news_item.get('title', '')} "
        f"{article_text[:EVENT_TEXT_LIMIT]}"
    )

    return {
        "topics": sorted(_event_topic_families(news_item)),
        "tokens": sorted(_meaningful_event_tokens(event_text)),
        "locations": sorted(_extract_location_tokens(event_text)),
    }


def compare_event_fingerprints(first_item, second_item):
    """Консервативно сравнивает два news_item как одно событие."""

    empty_result = {
        "is_duplicate": False,
        "shared_tokens": [],
        "shared_topics": [],
        "shared_locations": [],
        "token_overlap": 0.0,
        "token_jaccard": 0.0,
        "title_similarity": title_similarity(
            first_item.get("title", ""),
            second_item.get("title", ""),
        ),
        "time_delta_hours": None,
    }

    # Event-слой предназначен именно для разных СМИ.
    first_source = first_item.get("source")
    second_source = second_item.get("source")

    if first_source and second_source and first_source == second_source:
        return empty_result

    first_date = _parse_datetime(first_item.get("published_at"))
    second_date = _parse_datetime(second_item.get("published_at"))

    # Без двух надёжных дат риск false merge слишком велик.
    if first_date is None or second_date is None:
        return empty_result

    time_delta = abs(first_date - second_date)
    empty_result["time_delta_hours"] = time_delta.total_seconds() / 3600

    if time_delta > EVENT_TIME_WINDOW:
        return empty_result

    first_fingerprint = _read_or_build_fingerprint(first_item)
    second_fingerprint = _read_or_build_fingerprint(second_item)
    first_topics = set(first_fingerprint.get("topics", ()))
    second_topics = set(second_fingerprint.get("topics", ()))
    shared_topics = first_topics & second_topics

    if not shared_topics:
        return empty_result

    first_tokens = set(first_fingerprint.get("tokens", ()))
    second_tokens = set(second_fingerprint.get("tokens", ()))
    shared_tokens = first_tokens & second_tokens

    if not first_tokens or not second_tokens:
        return empty_result

    token_overlap = len(shared_tokens) / min(
        len(first_tokens),
        len(second_tokens),
    )
    token_union = first_tokens | second_tokens
    token_jaccard = len(shared_tokens) / len(token_union)
    shared_locations = (
        set(first_fingerprint.get("locations", ()))
        & set(second_fingerprint.get("locations", ()))
    )

    # Нужны минимум пять общих фактов и сильное покрытие меньшего текста.
    # География усиливает решение. Без неё требуется ещё более плотное
    # пересечение, чтобы разные убийства не слились случайно.
    has_enough_facts = (
        len(shared_tokens) >= MIN_SHARED_EVENT_TOKENS
        and token_overlap >= MIN_EVENT_TOKEN_OVERLAP
    )
    has_location_or_dense_match = bool(shared_locations) or (
        len(shared_tokens) >= 7
        and token_jaccard >= MIN_EVENT_TOKEN_JACCARD
    )

    return {
        **empty_result,
        "is_duplicate": bool(
            has_enough_facts and has_location_or_dense_match
        ),
        "shared_tokens": sorted(shared_tokens),
        "shared_topics": sorted(shared_topics),
        "shared_locations": sorted(shared_locations),
        "token_overlap": token_overlap,
        "token_jaccard": token_jaccard,
    }


def _read_or_build_fingerprint(news_item):
    """Читает сохранённый fingerprint или строит его для текущей новости."""

    fingerprint = news_item.get("event_fingerprint")

    if isinstance(fingerprint, dict):
        return fingerprint

    return build_event_fingerprint(news_item)


def _event_topic_families(news_item):
    """Приводит matched serious topics к крупным безопасным категориям."""

    topic_text = " ".join(news_item.get("strong_topics", ())).casefold()
    families = set()

    for family, markers in EVENT_TOPIC_FAMILIES.items():
        if any(marker in topic_text for marker in markers):
            families.add(family)

    return families


def _meaningful_event_tokens(text):
    """Возвращает значимые токены без процедурного шума."""

    tokens = set()

    for raw_token in re.findall(r"[а-яёa-z-]+", text.casefold()):
        if len(raw_token) < 4 or raw_token in EVENT_STOP_WORDS:
            continue

        token = _stem_russian_token(raw_token)

        if len(token) < 4:
            continue

        if any(token.startswith(prefix) for prefix in EVENT_NOISE_PREFIXES):
            continue

        if any(
            marker in token
            for markers in EVENT_TOPIC_FAMILIES.values()
            for marker in markers
        ):
            continue

        tokens.add(token)

    return tokens


def _extract_location_tokens(text):
    """Извлекает явные географические названия после предлогов места."""

    return {
        _stem_russian_token(match.group(1).casefold())
        for match in LOCATION_PATTERN.finditer(text)
    }


def _stem_russian_token(token):
    """Снимает несколько частых окончаний без внешней морфологии."""

    normalized = token.casefold().replace("ё", "е").strip("-")

    for suffix in RUSSIAN_INFLECTION_SUFFIXES:
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 4:
            normalized = normalized[:-len(suffix)]
            break

    # Охотник/охотника и похожие роли получают общий корень.
    for suffix in ("ник", "ниц"):
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 4:
            normalized = normalized[:-len(suffix)]
            break

    return normalized


def _parse_datetime(value):
    """Читает datetime текущей новости и ISO-дату из history."""

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None

    if not isinstance(value, datetime):
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _choose_preferred_event_item(first_item, second_item):
    """Выбирает score, затем полноту текста/картинки, затем первый item."""

    first_score = first_item.get("score", 0)
    second_score = second_item.get("score", 0)

    if first_score != second_score:
        return first_item if first_score > second_score else second_item

    def quality(item):
        article_text = item.get("article_text", "")
        return (
            bool(article_text),
            bool(item.get("image_url")),
            len(article_text),
        )

    if quality(second_item) > quality(first_item):
        return second_item

    return first_item


def _print_event_duplicate(first_item, second_item, details, preferred_item):
    """Печатает безопасную DRY_RUN-диагностику объединённого события."""

    print("[EVENT DEDUP]")
    print("Duplicate:")
    print(f"Source A: {first_item.get('source', 'не указан')}")
    print(f"Title A: {first_item.get('title', '')}")
    print()
    print(f"Source B: {second_item.get('source', 'не указан')}")
    print(f"Title B: {second_item.get('title', '')}")
    print()
    print("Reason:")
    print(f"shared tokens: {', '.join(details['shared_tokens'])}")
    print(f"topic: {', '.join(details['shared_topics'])}")
    print(
        "similarity: "
        f"title={details['title_similarity']:.3f}, "
        f"overlap={details['token_overlap']:.3f}, "
        f"jaccard={details['token_jaccard']:.3f}"
    )
    print(
        "kept: "
        f"{preferred_item.get('source', 'не указан')} — "
        f"{preferred_item.get('title', '')}"
    )
    print()
