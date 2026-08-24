import re
from difflib import SequenceMatcher


def normalize_title(title):
    """
    Приводит заголовок к единому виду
    для корректного сравнения.
    """

    # Переводим заголовок в нижний регистр.
    normalized = title.lower()

    # Убираем знаки препинания.
    normalized = re.sub(r"[^\w\s]", " ", normalized)

    # Убираем лишние пробелы.
    normalized = " ".join(normalized.split())

    return normalized


def remove_duplicates(news_items):
    """
    Удаляет:
    1. точные дубли по URL;
    2. точные дубли по заголовку;
    3. очень похожие заголовки.
    """

    unique_news = []
    seen_urls = set()

    for news_item in news_items:
        url = news_item["url"]

        # Точный дубль URL.
        if url in seen_urls:
            continue

        is_similar_duplicate = False

        # Сравниваем заголовок с уже оставленными новостями.
        for unique_item in unique_news:
            if titles_are_similar(
                news_item["title"],
                unique_item["title"],
            ):
                is_similar_duplicate = True
                break

        if is_similar_duplicate:
            continue

        seen_urls.add(url)
        unique_news.append(news_item)

    return unique_news


def titles_are_similar(title_1, title_2, threshold=0.75):
    """
    Проверяет, насколько два заголовка похожи.

    threshold=0.75 означает:
    считаем заголовки похожими, если совпадение 75% и выше.
    """

    first = normalize_title(title_1)
    second = normalize_title(title_2)

    similarity = SequenceMatcher(
        None,
        first,
        second,
    ).ratio()

    return similarity >= threshold
