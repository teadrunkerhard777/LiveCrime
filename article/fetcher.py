from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# Начала служебных абзацев, которые не относятся к телу статьи.
# Список находится в одном месте, чтобы его было легко расширять.
SERVICE_PARAGRAPH_PREFIXES = (
    "фото:",
    "видео:",
    "ранее сообщалось",
    "ранее стало известно",
    "напомним",
    "читайте также",
    "реклама",
)


def fetch_article_html(url):
    """
    Загружает HTML страницы новости.
    """

    # Многие сайты ожидают заголовок обычного браузера
    # и без него могут вернуть ошибку или пустую страницу.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        )
    }

    # timeout не позволяет программе ждать ответ бесконечно.
    response = requests.get(
        url,
        headers=headers,
        timeout=15,
    )

    # Сразу сообщаем об HTTP-ошибках вроде 404 или 500.
    response.raise_for_status()

    return response.text


def extract_article_text(html):
    """
    Извлекает текстовые абзацы из HTML страницы.
    Пока используем общий вариант без привязки к конкретному сайту.
    """

    # BeautifulSoup превращает HTML в удобное для поиска дерево.
    soup = BeautifulSoup(html, "html.parser")

    paragraphs = []

    # Собираем текст из всех абзацев страницы.
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(
            " ",
            strip=True,
        )

        # Сохраняем любой непустой абзац.
        # Короткая строка тоже может содержать важную информацию.
        if text:
            paragraphs.append(text)

    # Возвращаем одну обычную строку с разделёнными абзацами.
    return "\n\n".join(paragraphs)


def extract_article_image_url(html, page_url):
    """Возвращает URL основной картинки статьи или None."""

    soup = BeautifulSoup(html, "html.parser")

    # Open Graph обычно содержит основную картинку для соцсетей.
    image_meta = soup.find(
        "meta",
        attrs={"property": "og:image"},
    )

    # Twitter Card используем только как запасной стандартный источник.
    if image_meta is None:
        image_meta = soup.find(
            "meta",
            attrs={"name": "twitter:image"},
        )

    if image_meta is None:
        return None

    image_url = image_meta.get("content", "").strip()

    if not image_url:
        return None

    # urljoin сохраняет абсолютный URL и раскрывает относительный.
    return urljoin(page_url, image_url)


def clean_article_text(article_text):
    """
    Удаляет служебные абзацы из извлечённого текста статьи.
    """

    clean_paragraphs = []

    # extract_article_text разделяет абзацы пустой строкой.
    for paragraph in article_text.split("\n\n"):
        # Нормализуем пробелы, но не меняем содержимое абзаца.
        paragraph = " ".join(paragraph.split())

        if not paragraph:
            continue

        # Сравниваем без учёта регистра, чтобы правило работало
        # и для "Фото:", и для "ФОТО:".
        normalized_paragraph = paragraph.casefold()

        # Подписи к фото, ссылки на прошлые материалы
        # и похожие вставки не должны попадать в текст поста.
        is_service_paragraph = normalized_paragraph.startswith(
            SERVICE_PARAGRAPH_PREFIXES
        )

        if is_service_paragraph:
            continue

        clean_paragraphs.append(paragraph)

    return "\n\n".join(clean_paragraphs)
