import re


def normalize_title(title):
    """
    Приводит заголовок к более удобному виду
    для сравнения дублей.
    """

    # Переводим в нижний регистр.
    normalized = title.lower()

    # Убираем знаки препинания.
    normalized = re.sub(r"[^\w\s]", " ", normalized)

    # Убираем лишние пробелы.
    normalized = " ".join(normalized.split())

    return normalized


def remove_duplicates(news_items):
    """
    Удаляет точные дубли по URL и заголовку.
    """

    unique_news = []

    seen_urls = set()
    seen_titles = set()

    for news_item in news_items:
        url = news_item["url"]
        title = normalize_title(news_item["title"])

        # Если такой URL уже встречался,
        # пропускаем новость.
        if url in seen_urls:
            continue

        # Если такой заголовок уже встречался,
        # тоже считаем новость дублем.
        if title in seen_titles:
            continue

        seen_urls.add(url)
        seen_titles.add(title)

        unique_news.append(news_item)

    return unique_news
