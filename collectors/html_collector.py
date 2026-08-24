import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, FeatureNotFound
from bs4.exceptions import ParserRejectedMarkup


# HTML-источники отделены от RSS, потому что у каждого сайта
# своя разметка и свои правила поиска карточек новостей.
DEFAULT_NEWS_LIMIT = 40
REQUEST_TIMEOUT = 15

# Заголовок обычного браузера уменьшает число ошибочных блокировок.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}

# Русские названия месяцев нужны для дат на 116.ru и E1.ru.
RUSSIAN_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


def collect_html(source):
    """
    Получает новости с HTML-страницы через выбранный адаптер.

    Результат имеет тот же формат, что и collect_rss().
    Поэтому остальной pipeline не знает тип исходного источника.
    """

    adapter_name = source.get("adapter", "")
    adapter = ADAPTERS.get(adapter_name)

    # Неизвестный адаптер считаем ошибкой конфигурации,
    # но не останавливаем сбор из остальных источников.
    if adapter is None:
        print(
            "Предупреждение HTML: неизвестный адаптер "
            f"{adapter_name!r} для {source.get('name', 'источника')}."
        )
        return []

    try:
        # Загружаем только первую страницу указанной рубрики.
        response = requests.get(
            source["url"],
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        # Передаём bytes, чтобы BeautifulSoup сам прочитал кодировку HTML.
        soup = BeautifulSoup(response.content, "html.parser")
        news_items = adapter(soup, source)

    except requests.RequestException as error:
        # HTTP 403, timeout и другие сетевые ошибки одного сайта
        # не должны мешать работе остальных источников.
        print(
            f"Предупреждение HTML ({source.get('name', 'источник')}): "
            f"не удалось загрузить страницу ({type(error).__name__})."
        )
        return []

    except (
        FeatureNotFound,
        ParserRejectedMarkup,
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        # Такая ошибка может означать, что сайт изменил вёрстку.
        print(
            f"Предупреждение HTML ({source.get('name', 'источник')}): "
            f"не удалось разобрать страницу ({type(error).__name__})."
        )
        return []

    if not news_items:
        print(
            f"Предупреждение HTML ({source.get('name', 'источник')}): "
            "карточки новостей не найдены; возможно, изменилась вёрстка."
        )
        return []

    # Ограничиваем объём одной страницей и разумным числом карточек.
    limit = source.get("limit", DEFAULT_NEWS_LIMIT)

    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = DEFAULT_NEWS_LIMIT

    return news_items[:limit]


def collect_116ru(soup, source):
    """Разбирает рубрику происшествий 116.ru."""

    return _collect_ngs_news(
        soup,
        source,
        default_timezone="Europe/Moscow",
    )


def collect_e1ru(soup, source):
    """Разбирает рубрику происшествий E1.ru."""

    # E1.ru и 116.ru работают на одной платформе,
    # но остаются отдельными адаптерами для будущих отличий.
    return _collect_ngs_news(
        soup,
        source,
        default_timezone="Asia/Yekaterinburg",
    )


def collect_vnru(soup, source):
    """Разбирает рубрику происшествий VN.ru."""

    news_items = []
    timezone_name = source.get(
        "timezone",
        "Asia/Novosibirsk",
    )

    # У VN.ru одна новость находится внутри отдельного article.
    for card in soup.select("article.section_news_item"):
        title_link = card.select_one(
            ".section_news_item_content_title a[href]"
        )

        # Частично сломанная карточка просто пропускается.
        if title_link is None:
            continue

        title = _clean_text(title_link.get_text(" ", strip=True))
        article_url = urljoin(
            source["url"],
            title_link.get("href", ""),
        )

        # Берём только прямые статьи самого VN.ru.
        if not title or not _is_direct_vn_article(article_url, source):
            continue

        date_node = card.select_one(".section_news_item_date")
        description_node = card.select_one(
            ".section_news_item_content_preview"
        )

        date_text = (
            date_node.get_text(" ", strip=True)
            if date_node is not None
            else ""
        )
        description = (
            _clean_text(description_node.get_text(" ", strip=True))
            if description_node is not None
            else ""
        )

        news_items.append(
            _build_news_item(
                title=title,
                url=article_url,
                published_at=_parse_publication_date(
                    date_text,
                    timezone_name,
                ),
                description=description,
                source=source,
            )
        )

    return news_items


def _collect_ngs_news(soup, source, default_timezone):
    """Общая логика карточек платформы 116.ru / E1.ru."""

    news_by_url = {}
    timezone_name = source.get("timezone", default_timezone)

    # Хешированные CSS-классы могут меняться после сборки сайта.
    # Поэтому основу поиска составляет стабильный формат прямого URL.
    for anchor in soup.find_all("a", href=True):
        article_url = urljoin(source["url"], anchor["href"])

        if not _is_direct_ngs_article(article_url, source):
            continue

        title = _clean_text(
            anchor.get("data-announcement-title")
            or anchor.get("title")
            or anchor.get_text(" ", strip=True)
        )

        if not title:
            continue

        # Подзаголовок доступен у основной карточки, но может отсутствовать.
        description = ""
        date_text = ""

        if anchor.get("data-announcement-title"):
            subtitle = anchor.find_next_sibling("span")

            if subtitle is not None:
                description = _clean_text(
                    subtitle.get_text(" ", strip=True)
                )

            date_text = _find_announcement_date(anchor)

        page_date = _parse_publication_date(
            date_text,
            timezone_name,
        )
        url_date = _parse_ngs_url_date(
            article_url,
            timezone_name,
        )

        existing = news_by_url.get(article_url)

        if existing is None:
            news_by_url[article_url] = _build_news_item(
                title=title,
                url=article_url,
                published_at=page_date or url_date,
                description=description,
                source=source,
            )
            continue

        # Одна карточка обычно содержит ссылку в картинке и заголовке.
        # Объединяем их, а не создаём дубли одной статьи.
        if len(title) > len(existing["title"]):
            existing["title"] = title

        if description and not existing["description"]:
            existing["description"] = description

        if page_date is not None:
            existing["published_at"] = page_date

    # Самые свежие материалы должны попадать в лимит первыми.
    return sorted(
        news_by_url.values(),
        key=lambda item: (
            item["published_at"]
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )


def _build_news_item(
    title,
    url,
    published_at,
    description,
    source,
):
    """Создаёт news_item в едином для RSS и HTML формате."""

    return {
        "title": title,
        "url": url,
        "published_at": published_at,
        "description": description,
        "source": source["name"],
    }


def _find_announcement_date(anchor):
    """Ищет дату в ближайшей карточке 116.ru или E1.ru."""

    node = anchor

    # Поднимаемся только в пределах небольшой карточки,
    # чтобы не взять дату соседней публикации.
    for _ in range(5):
        node = node.parent

        if node is None:
            break

        date_node = node.find(
            attrs={"data-announcement-date": True}
        )

        if date_node is not None:
            return date_node.get("data-announcement-date", "")

    return ""


def _parse_publication_date(date_text, timezone_name, now=None):
    """Преобразует абсолютную или относительную дату в aware datetime."""

    if not date_text:
        return None

    local_timezone = ZoneInfo(timezone_name)
    cleaned = _clean_text(date_text).casefold()

    # Обрабатываем варианты "Сегодня, 12:30" и "Вчера, 21:15".
    relative_match = re.fullmatch(
        r"(сегодня|вчера),?\s+(\d{1,2}):(\d{2})",
        cleaned,
    )

    if relative_match:
        current_time = (
            now.astimezone(local_timezone)
            if now is not None
            else datetime.now(local_timezone)
        )
        day_offset = 1 if relative_match.group(1) == "вчера" else 0
        local_date = (current_time - timedelta(days=day_offset)).date()

        return datetime(
            local_date.year,
            local_date.month,
            local_date.day,
            int(relative_match.group(2)),
            int(relative_match.group(3)),
            tzinfo=local_timezone,
        )

    # VN.ru использует короткую запись вида 24.08.2026.
    try:
        parsed_date = datetime.strptime(cleaned, "%d.%m.%Y")
        return parsed_date.replace(tzinfo=local_timezone)
    except ValueError:
        pass

    # 116.ru и E1.ru используют вид "24 августа, 2026, 07:33".
    russian_date_match = re.fullmatch(
        r"(\d{1,2})\s+([а-яё]+),?\s+(\d{4})"
        r"(?:,?\s+(\d{1,2}):(\d{2}))?",
        cleaned,
    )

    if russian_date_match is None:
        return None

    month = RUSSIAN_MONTHS.get(russian_date_match.group(2))

    if month is None:
        return None

    hour = int(russian_date_match.group(4) or 0)
    minute = int(russian_date_match.group(5) or 0)

    try:
        return datetime(
            int(russian_date_match.group(3)),
            month,
            int(russian_date_match.group(1)),
            hour,
            minute,
            tzinfo=local_timezone,
        )
    except ValueError:
        return None


def _parse_ngs_url_date(article_url, timezone_name):
    """Использует дату из прямого URL, если карточка её не показала."""

    date_match = re.search(
        r"/text/incidents/(\d{4})/(\d{2})/(\d{2})/\d+/?$",
        urlparse(article_url).path,
    )

    if date_match is None:
        return None

    try:
        return datetime(
            int(date_match.group(1)),
            int(date_match.group(2)),
            int(date_match.group(3)),
            tzinfo=ZoneInfo(timezone_name),
        )
    except ValueError:
        return None


def _is_direct_ngs_article(article_url, source):
    """Проверяет домен и формат прямой ссылки 116.ru / E1.ru."""

    article_parts = urlparse(article_url)
    source_parts = urlparse(source["url"])

    return (
        _normalized_host(article_parts.netloc)
        == _normalized_host(source_parts.netloc)
        and re.fullmatch(
            r"/text/incidents/\d{4}/\d{2}/\d{2}/\d+/?",
            article_parts.path,
        )
        is not None
    )


def _is_direct_vn_article(article_url, source):
    """Проверяет, что URL ведёт на оригинальную статью VN.ru."""

    article_parts = urlparse(article_url)
    source_parts = urlparse(source["url"])

    return (
        _normalized_host(article_parts.netloc)
        == _normalized_host(source_parts.netloc)
        and article_parts.path.startswith("/news-")
        and article_parts.path.endswith("/")
    )


def _normalized_host(host):
    """Считает домены с www и без www одним сайтом."""

    return host.casefold().removeprefix("www.")


def _clean_text(text):
    """Убирает лишние пробелы из текста карточки."""

    return " ".join((text or "").split())


# Имя adapter из config.py явно выбирает небольшую функцию сайта.
# Для нового источника достаточно добавить функцию и одну запись здесь.
ADAPTERS = {
    "116ru": collect_116ru,
    "e1ru": collect_e1ru,
    "vnru": collect_vnru,
}
