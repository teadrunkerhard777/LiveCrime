from html import escape

from config import TOPIC_TAGS


# Telegram sendMessage принимает до 4096 символов.
# Оставляем небольшой запас на возможные будущие элементы шаблона.
TELEGRAM_SAFE_LIMIT = 4000

# Telegram photo caption ограничен 1024 символами после разбора HTML.
# Лимит 1000 оставляет небольшой запас и учитывает разметку консервативно.
TELEGRAM_PHOTO_CAPTION_SAFE_LIMIT = 1000
TITLE_SAFE_LIMIT = 500

RUSSIAN_MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def generate_post(news_item):
    """Формирует безопасный Telegram-пост с минимальной HTML-разметкой."""

    return _generate_post(news_item, TELEGRAM_SAFE_LIMIT)


def generate_photo_caption(news_item):
    """Формирует компактную подпись для одного Telegram photo-сообщения."""

    # Отдельный короткий лимит нужен только для caption у sendPhoto.
    return _generate_post(news_item, TELEGRAM_PHOTO_CAPTION_SAFE_LIMIT)


def _generate_post(news_item, safe_limit):
    """Собирает общий HTML-шаблон с заданным безопасным лимитом."""

    # Заголовок ограничиваем отдельно, чтобы он не вытеснил весь текст.
    raw_title = truncate_article_text(
        news_item.get("title", ""),
        TITLE_SAFE_LIMIT,
    )
    title = escape(raw_title)

    # Полный текст предпочтительнее RSS description.
    # Если оба пусты, пост всё равно сохранит заголовок и метаданные.
    raw_article_text = (
        news_item.get("article_text")
        or news_item.get("description", "")
    )

    source = escape(news_item.get("source", "Источник неизвестен"))
    url = escape(news_item.get("url", ""), quote=True)
    date_text = _format_date(news_item.get("published_at"))
    tags_text = generate_tags(news_item, TOPIC_TAGS)

    header = f"🔴 <b>{title}</b>"
    footer = (
        f"📅 {date_text}\n"
        f"📰 {source}\n\n"
        f'🔗 <a href="{url}">Читать источник</a>'
    )

    # Теги идут обычным текстом после ссылки и не входят в HTML-теги.
    if tags_text:
        footer = f"{footer}\n\n{tags_text}"

    # Рассчитываем место после готовых заголовка и метаданных.
    # Лимит учитывает экранированный HTML, включая &amp; и &lt;.
    fixed_length = len(header) + len(footer) + 4
    article_limit = max(0, safe_limit - fixed_length)
    article_text = truncate_article_text(raw_article_text, article_limit)
    escaped_article_text = escape(article_text)

    if escaped_article_text:
        return f"{header}\n\n{escaped_article_text}\n\n{footer}"

    return f"{header}\n\n{footer}"


def generate_tags(news_item, topic_tags, max_tags=4):
    """Преобразует matched_topics в уникальную строку хэштегов."""

    generated_tags = []
    seen_tags = set()

    # Порядок matched_topics отражает порядок тематик в config.py.
    for topic in news_item.get("matched_topics", []):
        tag = topic_tags.get(topic)

        if not tag or tag in seen_tags:
            continue

        # Удаляем дубли по готовому тегу: розыск и разыск дадут один тег.
        generated_tags.append(tag)
        seen_tags.add(tag)

        # Небольшой лимит не перегружает конец Telegram-поста.
        if len(generated_tags) >= max_tags:
            break

    return " ".join(generated_tags)


def truncate_article_text(text, max_escaped_length):
    """Сокращает текст по границе предложения или слова."""

    cleaned_text = _clean_article_spacing(text)

    if not cleaned_text or max_escaped_length <= 0:
        return ""

    # html.escape() может увеличить длину строки.
    if len(escape(cleaned_text)) <= max_escaped_length:
        return cleaned_text

    ellipsis = "…"
    available_length = max_escaped_length - len(ellipsis)

    if available_length <= 0:
        return ""

    # Двоичный поиск быстро находит максимальный безопасный сырой префикс.
    low = 0
    high = len(cleaned_text)

    while low < high:
        middle = (low + high + 1) // 2

        if len(escape(cleaned_text[:middle])) <= available_length:
            low = middle
        else:
            high = middle - 1

    candidate = cleaned_text[:low].rstrip()

    # Сначала стараемся закончить на последнем полном предложении.
    sentence_end = max(
        candidate.rfind(". "),
        candidate.rfind("! "),
        candidate.rfind("? "),
        candidate.rfind(".\n"),
        candidate.rfind("!\n"),
        candidate.rfind("?\n"),
    )

    if sentence_end >= len(candidate) // 2:
        candidate = candidate[:sentence_end + 1].rstrip()
    else:
        # Если полного предложения рядом нет, не режем последнее слово.
        word_end = max(candidate.rfind(" "), candidate.rfind("\n"))

        if word_end > 0:
            candidate = candidate[:word_end].rstrip()

    return f"{candidate}{ellipsis}" if candidate else ""


def _format_date(published_at):
    """Выводит дату с русским названием месяца без locale-зависимости."""

    if published_at is None:
        return "Дата неизвестна"

    month = RUSSIAN_MONTHS[published_at.month]
    return f"{published_at.day} {month} {published_at.year}"


def _clean_article_spacing(text):
    """Убирает лишние пробелы, сохраняя абзацы статьи."""

    paragraphs = [
        " ".join(paragraph.split())
        for paragraph in (text or "").splitlines()
        if paragraph.strip()
    ]
    return "\n\n".join(paragraphs)
