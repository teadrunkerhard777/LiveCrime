import requests
from bs4 import BeautifulSoup


def fetch_article_html(url):
    """
    Загружает HTML страницы новости.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=15,
    )

    response.raise_for_status()

    return response.text


def extract_article_text(html):
    """
    Извлекает текстовые абзацы из HTML страницы.
    Пока используем общий вариант без привязки к конкретному сайту.
    """

    soup = BeautifulSoup(html, "html.parser")

    paragraphs = []

    # Собираем текст из всех абзацев страницы.
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(
            " ",
            strip=True,
        )

        # Совсем короткие строки обычно являются
        # служебными элементами, поэтому их пропускаем.
        if len(text) >= 40:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)
