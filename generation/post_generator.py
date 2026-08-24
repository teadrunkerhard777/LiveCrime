def generate_post(news_item):
    """
    Формирует простой Telegram-пост
    из уже отобранной новости.
    """

    title = news_item["title"]
    description = news_item["description"]
    source = news_item["source"]
    published_at = news_item["published_at"]
    url = news_item["url"]

    # Дату выводим в понятном формате.
    if published_at:
        date_text = published_at.strftime("%d.%m.%Y")
    else:
        date_text = "Дата неизвестна"

    # Пока используем простой шаблон.
    post = (
        f"🔴 {title}\n\n"
        f"{description}\n\n"
        f"📅 {date_text}\n"
        f"Источник: {source}\n"
        f"{url}"
    )

    return post
