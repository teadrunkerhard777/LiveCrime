import json
from pathlib import Path


HISTORY_FILE = Path("storage/published.json")


def load_history():
    """
    Загружает историю уже обработанных новостей.
    """

    # Если файла ещё нет, возвращаем пустой список.
    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        # Если файл повреждён или не читается,
        # пока не останавливаем всю программу.
        return []


def save_history(history):
    """
    Сохраняет историю обработанных новостей.
    """

    with HISTORY_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2,
        )


def is_published(news_item, history):
    """
    Проверяет, встречалась ли новость раньше.

    Пока сравниваем по URL.
    Этого достаточно для первой версии истории.
    """

    news_url = news_item["url"]

    for item in history:
        if item.get("url") == news_url:
            return True

    return False


def add_to_history(news_item, history):
    """
    Добавляет новость в историю обработанных материалов.
    """

    history.append(
        {
            "title": news_item["title"],
            "url": news_item["url"],
            "published_at": (
                news_item["published_at"].isoformat()
                if news_item["published_at"]
                else None
            ),
        }
    )

    return history
