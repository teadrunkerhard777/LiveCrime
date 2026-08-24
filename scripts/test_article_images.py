"""Безопасно проверяет основные картинки свежих статей Lenta.ru."""

import sys
from pathlib import Path

import requests
from bs4 import FeatureNotFound
from bs4.exceptions import ParserRejectedMarkup


# Позволяет запускать файл напрямую: python scripts/test_article_images.py.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from article.fetcher import extract_article_image_url, fetch_article_html
from collectors.rss_collector import collect_rss
from config import SOURCES
from core.environment import configure_ssl


ARTICLE_LIMIT = 15
IMAGE_CHECK_TIMEOUT = 15
IMAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}


def _is_available_image(response):
    """Проверяет успешный статус и MIME-тип без чтения всего файла."""

    content_type = response.headers.get("Content-Type", "")
    return (
        response.status_code == 200
        and content_type.casefold().startswith("image/")
    )


def check_image_url(image_url):
    """Проверяет URL через HEAD и безопасный streaming GET fallback."""

    try:
        # HEAD обычно позволяет проверить картинку без загрузки тела ответа.
        with requests.head(
            image_url,
            headers=IMAGE_HEADERS,
            timeout=IMAGE_CHECK_TIMEOUT,
            allow_redirects=True,
        ) as response:
            if _is_available_image(response):
                return True

    except requests.RequestException:
        # Некоторые CDN не поддерживают HEAD, поэтому пробуем GET ниже.
        pass

    try:
        # stream=True не загружает всё изображение в память или на диск.
        with requests.get(
            image_url,
            headers=IMAGE_HEADERS,
            timeout=IMAGE_CHECK_TIMEOUT,
            allow_redirects=True,
            stream=True,
        ) as response:
            return _is_available_image(response)

    except requests.RequestException:
        return False


def get_lenta_source():
    """Находит существующую конфигурацию RSS Lenta.ru."""

    for source in SOURCES:
        if source.get("name") == "Lenta.ru":
            return source

    raise RuntimeError("Источник Lenta.ru не найден в config.py.")


def run_diagnostics(
    news_items=None,
    article_limit=ARTICLE_LIMIT,
    fetch_html=fetch_article_html,
    check_image=check_image_url,
):
    """Печатает URL картинок и возвращает итоговые счётчики."""

    if news_items is None:
        news_items = collect_rss(get_lenta_source())

    # RSS уже отсортирован от новых публикаций к более старым.
    selected_news = [
        item for item in news_items
        if item.get("url")
    ][:article_limit]

    found_count = 0
    available_count = 0
    not_found_count = 0

    for number, news_item in enumerate(selected_news, start=1):
        title = news_item.get("title", "")
        page_url = news_item["url"]
        image_url = None

        print("=" * 60)
        print(f"Статья {number}/{len(selected_news)}")
        print(f"Заголовок: {title}")
        print(f"URL статьи: {page_url}")

        try:
            # Один HTML-запрос достаточен для извлечения URL картинки.
            html = fetch_html(page_url)
            image_url = extract_article_image_url(html, page_url)

        except (
            requests.RequestException,
            FeatureNotFound,
            ParserRejectedMarkup,
        ) as error:
            print("Image URL: NOT FOUND")
            print(f"Доступность: ERROR ({type(error).__name__})")
            not_found_count += 1
            continue

        if not image_url:
            print("Image URL: NOT FOUND")
            print("Доступность: NO")
            not_found_count += 1
            continue

        found_count += 1
        print(f"Image URL: {image_url}")

        # Ошибка одной картинки не останавливает остальные проверки.
        is_available = check_image(image_url)
        print(f"Доступность: {'YES' if is_available else 'NO'}")

        if is_available:
            available_count += 1

    summary = {
        "checked": len(selected_news),
        "found": found_count,
        "available": available_count,
        "not_found": not_found_count,
    }

    print("=" * 60)
    print(f"Проверено статей: {summary['checked']}")
    print(f"Image URL найдено: {summary['found']}")
    print(f"Изображений доступно: {summary['available']}")
    print(f"NOT FOUND: {summary['not_found']}")

    return summary


if __name__ == "__main__":
    # SSL настраивается так же, как в основном приложении.
    configure_ssl()
    run_diagnostics()
