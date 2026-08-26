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


# Эти маркеры относятся только к footer сайта PeterburgMedia.
# Первый найденный маркер завершает полезную часть статьи целиком.
PETERBURGMEDIA_STOP_MARKERS = (
    "push-уведомления",
    "читайте наши новости в telegram",
    "подписывайтесь на новости peterburgmedia во вконтакте",
    "информация для пользователей 18+",
    "отправить сообщение в редакцию сайта?",
    "электронный ресурс (сайт) использует cookies",
    "политикой обработки персональных данных",
    "согласием на обработку персональных данных",
    "на сайте используются рекомендательные технологии",
)


# Footer VN.ru обычно находится вне article body, но эти маркеры дают
# дополнительную страховку при будущих изменениях вёрстки сайта.
VN_STOP_MARKERS = (
    "© 2015 -",
    "все новости новосибирской области",
    "свидетельство о регистрации сми",
    "роскомнадзор",
    "учредитель",
    "главный редактор",
    "телефон редакции",
    "электронный адрес редакции",
    "по вопросам партнерства",
    "рекомендательные технологии",
    "политика конфиденциальности",
)


# Новые сайты можно подключать здесь, не добавляя условия в main.py.
SOURCE_STOP_MARKERS = {
    "PeterburgMedia: происшествия": PETERBURGMEDIA_STOP_MARKERS,
    "VN.ru: происшествия": VN_STOP_MARKERS,
}


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


def extract_article_text(html, source=None):
    """
    Извлекает текстовые абзацы из HTML страницы.
    Пока используем общий вариант без привязки к конкретному сайту.
    """

    # BeautifulSoup превращает HTML в удобное для поиска дерево.
    soup = BeautifulSoup(html, "html.parser")

    # Для сайтов с надёжным article body используем отдельный extractor.
    # Если VN-контейнер не найден, случайные <p> всей страницы не собираем.
    source_extractor = SOURCE_TEXT_EXTRACTORS.get(source)

    if source_extractor is not None:
        return source_extractor(soup)

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


def extract_vn_article_text(soup):
    """Извлекает только тело текущей статьи VN.ru."""

    article_body = soup.select_one(
        '#newstext.one-news-text[itemprop="articleBody"]'
    )

    if article_body is None:
        return ""

    # Контейнер должен находиться в том же article, что и текущий h1.
    # Это не даёт принять карточку соседней новости за основной материал.
    current_article = article_body.find_parent("article")

    if (
        current_article is None
        or current_article.select_one("h1.det_news_title") is None
    ):
        return ""

    # Related-карточки иногда встроены прямо в первый абзац body.
    # Удаляем их до get_text(), не затрагивая основной текст вокруг.
    for related_block in article_body.select(
        "aside.divider, .news-block-cit, .related-news, .recommendation"
    ):
        related_block.decompose()

    paragraphs = []

    # На VN.ru абзацы статьи — прямые дочерние div, а не теги <p>.
    for block in article_body.find_all(["div", "p"], recursive=False):
        text = block.get_text(" ", strip=True)

        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


# Эти вложенные блоки подтверждены на сайтах Media-семейства.
# Они находятся внутри article body, но не относятся к тексту новости.
MEDIA_FAMILY_SERVICE_SELECTORS = (
    ".noprint",
    ".news_links_related",
    ".page-content__related",
)


def extract_media_family_article_text(soup):
    """Извлекает только тело текущей статьи Media-семейства."""

    article_body = soup.select_one(
        '.page-content.io-article-body[itemprop="articleBody"]'
    )

    if article_body is None:
        return ""

    # Article body должен находиться рядом с h1 текущей новости.
    # Так соседние карточки и общий footer страницы не попадут в результат.
    current_article = article_body.find_parent(
        "div",
        class_="page-fullnews",
    )

    if current_article is None or current_article.select_one("h1") is None:
        return ""

    # Удаляем рекламу, соцблоки, навигацию и related links до get_text().
    # DOM-селекторы не затрагивают обычные содержательные абзацы.
    for service_block in article_body.select(
        ", ".join(MEDIA_FAMILY_SERVICE_SELECTORS)
    ):
        service_block.decompose()

    paragraphs = []

    # Берём абзацы только из надёжного article body.
    # Footer и соседние новости находятся за его границами.
    for paragraph in article_body.find_all("p"):
        text = paragraph.get_text(" ", strip=True)

        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_agn_moscow_article_text(soup):
    """Извлекает только тело текущего материала АГН Москва."""

    article_body = soup.select_one(
        '#Article.article > div.text[itemprop="articleBody"]'
    )

    if article_body is None:
        return ""

    # Проверяем, что body связан с h1 именно текущего материала.
    # Служебное время находится рядом с h1, но не внутри article body.
    current_article = article_body.find_parent(
        "div",
        id="Article",
    )

    if (
        current_article is None
        or current_article.select_one(
            'h1.title[itemprop="headline"]'
        ) is None
    ):
        return ""

    paragraphs = []

    # На реальных страницах содержательные абзацы являются прямыми
    # дочерними <p>. Header, дата и footer остаются за границами body.
    for paragraph in article_body.find_all("p", recursive=False):
        text = paragraph.get_text(" ", strip=True)

        # Короткие содержательные абзацы тоже сохраняются.
        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_amic_article_text(soup):
    """Извлекает только редакционное тело статьи Amic.ru."""

    article_body = soup.select_one("#post.post > section.text")

    if article_body is None:
        return ""

    # Надёжный body должен относиться к тому же post, где находится h1.
    current_article = article_body.find_parent("div", id="post")

    if current_article is None or current_article.select_one("h1") is None:
        return ""

    paragraphs = []

    # Содержательные цитаты сохраняем вместе с обычными абзацами.
    # Inject-карточки соседних материалов имеют другой тип элемента.
    for block in article_body.find_all(
        ["p", "blockquote"],
        recursive=False,
    ):
        text = block.get_text(" ", strip=True)

        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_a42_article_text(soup):
    """Извлекает только редакционный текст материала A42."""

    article_body = soup.select_one(
        'article.material .material__body[itemprop="articleBody"]'
    )

    if article_body is None:
        return ""

    current_article = article_body.find_parent("article", class_="material")

    if current_article is None or current_article.select_one("h1") is None:
        return ""

    # Автор, категория и мобильная копия заголовка лежат рядом,
    # а полезные абзацы находятся только внутри rte-text.
    text_body = article_body.select_one(".rte-block.rte-text")

    if text_body is None:
        return ""

    paragraphs = []

    for paragraph in text_body.find_all("p"):
        text = paragraph.get_text(" ", strip=True)

        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


# Диспетчер сохраняет source-specific правила в одном модуле.
SOURCE_TEXT_EXTRACTORS = {
    "АГН Москва: происшествия": extract_agn_moscow_article_text,
    "VN.ru: происшествия": extract_vn_article_text,
    "KrasnoyarskMedia: происшествия": extract_media_family_article_text,
    "StolicaMedia: происшествия Москвы и области": (
        extract_media_family_article_text
    ),
    "AmurMedia: происшествия Хабаровского края": (
        extract_media_family_article_text
    ),
    "YakutiaMedia: происшествия": extract_media_family_article_text,
    "PriamurMedia: происшествия": extract_media_family_article_text,
    "KamchatkaMedia: происшествия": extract_media_family_article_text,
    "EAOMedia: происшествия": extract_media_family_article_text,
    "MagadanMedia: происшествия": extract_media_family_article_text,
    "ChukotkaMedia: происшествия": extract_media_family_article_text,
    "Amic.ru: происшествия": extract_amic_article_text,
    "A42: происшествия": extract_a42_article_text,
}


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


def clean_article_text(article_text, source=None):
    """
    Удаляет служебные абзацы из извлечённого текста статьи.
    """

    clean_paragraphs = []
    source_stop_markers = SOURCE_STOP_MARKERS.get(source, ())

    # extract_article_text разделяет абзацы пустой строкой.
    for paragraph in article_text.split("\n\n"):
        # Нормализуем пробелы, но не меняем содержимое абзаца.
        paragraph = " ".join(paragraph.split())

        if not paragraph:
            continue

        # Сравниваем без учёта регистра, чтобы правило работало
        # и для "Фото:", и для "ФОТО:".
        normalized_paragraph = paragraph.casefold()

        # Footer PeterburgMedia начинается с отдельного служебного абзаца.
        # Всё ниже уже относится к подпискам, cookies и информации сайта.
        has_source_footer_started = normalized_paragraph.startswith(
            source_stop_markers
        )

        if has_source_footer_started:
            break

        # Подписи к фото, ссылки на прошлые материалы
        # и похожие вставки не должны попадать в текст поста.
        is_service_paragraph = normalized_paragraph.startswith(
            SERVICE_PARAGRAPH_PREFIXES
        )

        if is_service_paragraph:
            continue

        clean_paragraphs.append(paragraph)

    return "\n\n".join(clean_paragraphs)
