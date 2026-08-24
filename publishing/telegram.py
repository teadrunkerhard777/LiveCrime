import os

import requests
from dotenv import load_dotenv


# Загружаем переменные из локального .env.
# Существующие переменные окружения при этом не перезаписываются.
load_dotenv()


def send_telegram_post(text):
    """
    Отправляет один текстовый пост через Telegram Bot API.

    Возвращает True только после подтверждения Telegram.
    При любой ошибке возвращает False и не прерывает программу.
    """

    # Токен и chat ID читаем только из окружения.
    # Секреты не должны храниться в исходном коде.
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Без обязательных настроек запрос всё равно не сможет пройти.
    if not bot_token or not chat_id:
        print(
            "Ошибка Telegram: заполните TELEGRAM_BOT_TOKEN "
            "и TELEGRAM_CHAT_ID в .env."
        )
        return False

    api_url = (
        f"https://api.telegram.org/bot{bot_token}/sendMessage"
    )

    # Пока отправляем обычный текст без HTML и Markdown-разметки.
    payload = {
        "chat_id": chat_id,
        "text": text,
    }

    try:
        # timeout не позволяет зависнуть при проблемах с сетью.
        response = requests.post(
            api_url,
            json=payload,
            timeout=15,
        )

        # HTTP-ошибки 4xx и 5xx считаем неуспешной отправкой.
        response.raise_for_status()

    except requests.HTTPError as error:
        status_code = (
            error.response.status_code
            if error.response is not None
            else "неизвестен"
        )
        print(
            "Ошибка Telegram: сервер вернул HTTP-статус "
            f"{status_code}."
        )
        return False

    except requests.RequestException as error:
        # Не печатаем URL запроса, потому что внутри него находится токен.
        print(
            "Ошибка Telegram: не удалось выполнить запрос "
            f"({type(error).__name__})."
        )
        return False

    try:
        # Telegram всегда возвращает JSON с логическим полем ok.
        response_data = response.json()

    except requests.exceptions.JSONDecodeError:
        print("Ошибка Telegram: сервер вернул некорректный JSON.")
        return False

    # Защищаемся от неожиданного JSON-формата без поля ok.
    if not isinstance(response_data, dict):
        print("Ошибка Telegram: неожиданный формат ответа.")
        return False

    # Даже при HTTP 200 Telegram может сообщить об ошибке через ok=False.
    if response_data.get("ok") is not True:
        description = response_data.get(
            "description",
            "причина не указана",
        )
        print(f"Ошибка Telegram: {description}.")
        return False

    return True
