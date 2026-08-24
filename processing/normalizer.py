from email.utils import parsedate_to_datetime
import re
from html import unescape


def normalize_date(date_string):
    """
    Преобразует дату из RSS в объект datetime.

    Пример входной строки:
    Fri, 21 Aug 2026 10:05:00 GMT
    """

    # Если дата отсутствует, возвращаем None.
    if not date_string:
        return None

    try:
        # parsedate_to_datetime умеет разбирать
        # стандартный формат дат RSS / email.
        return parsedate_to_datetime(date_string)

    except (TypeError, ValueError):
        # Если конкретный источник отдаст неожиданную дату,
        # программа не должна из-за этого падать.
        return None


def clean_description(description):
    """
    Убирает HTML-разметку и служебные символы
    из описания RSS.
    """

    if not description:
        return ""

    # Преобразуем HTML-сущности вроде &nbsp;
    cleaned = unescape(description)

    # Убираем HTML-теги.
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)

    # Убираем лишние пробелы.
    cleaned = " ".join(cleaned.split())

    return cleaned
