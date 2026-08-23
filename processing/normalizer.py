from email.utils import parsedate_to_datetime


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
