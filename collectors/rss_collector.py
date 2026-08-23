import feedparser

from processing.normalizer import normalize_date


def collect_rss(source):
    """
    Получает новости из одного RSS-источника.

    source ожидаем в таком формате:
    {
        "name": "...",
        "type": "rss",
        "url": "..."
    }
    """

    # Загружаем и разбираем RSS-ленту.
    feed = feedparser.parse(source["url"])

    # Если RSS разобрался с ошибкой, показываем её в терминале.
    if feed.bozo:
        print(f"Ошибка RSS: {feed.bozo_exception}")

    # Здесь будем собирать новости в едином формате.
    news_items = []

    # feed.entries содержит отдельные публикации из RSS.
    for entry in feed.entries:
        news_item = {
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "published_at": normalize_date(entry.get("published", "")),
            "description": entry.get("summary", ""),
            "source": source["name"],
        }

        news_items.append(news_item)

    return news_items
