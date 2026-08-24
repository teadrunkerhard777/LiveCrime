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

    success, error_reason = _send_telegram_request(
        "sendMessage",
        {
            "text": text,
            "parse_mode": "HTML",
        },
    )

    if not success:
        print(f"Ошибка Telegram: {error_reason}")

    return success


def send_telegram_photo(image_url, caption):
    """Отправляет картинку по URL и caption как одно Telegram-сообщение."""

    if not image_url:
        print("Ошибка Telegram: URL изображения не указан.")
        return False

    # Telegram сам получает изображение: локальный файл не создаётся.
    success, error_reason = _send_telegram_request(
        "sendPhoto",
        {
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        },
    )

    if not success:
        # URL безопасно показывать в Actions: токена в нём нет.
        print(f"Причина: {error_reason}")
        print(f"Image URL: {image_url}")

    return success


def _send_telegram_request(method, payload):
    """Возвращает пару: успех и безопасная причина ошибки."""

    # Токен и chat ID читаем только из окружения.
    # Секреты не должны храниться в исходном коде.
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Без обязательных настроек запрос всё равно не сможет пройти.
    if not bot_token or not chat_id:
        return (
            False,
            "не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID",
        )

    api_url = f"https://api.telegram.org/bot{bot_token}/{method}"

    # Telegram разберёт только минимальные теги <b> и <a>,
    # которые формирует и безопасно экранирует post_generator.py.
    request_payload = {"chat_id": chat_id, **payload}

    try:
        # timeout не позволяет зависнуть при проблемах с сетью.
        response = requests.post(
            api_url,
            json=request_payload,
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
        return (
            False,
            f"сервер вернул HTTP-статус {status_code}",
        )

    except requests.RequestException as error:
        # Не печатаем URL запроса, потому что внутри него находится токен.
        return (
            False,
            f"сетевая ошибка {type(error).__name__}",
        )

    try:
        # Telegram всегда возвращает JSON с логическим полем ok.
        response_data = response.json()

    except requests.exceptions.JSONDecodeError:
        return False, "сервер вернул некорректный JSON"

    # Защищаемся от неожиданного JSON-формата без поля ok.
    if not isinstance(response_data, dict):
        return False, "сервер вернул неожиданный формат ответа"

    # Даже при HTTP 200 Telegram может сообщить об ошибке через ok=False.
    if response_data.get("ok") is not True:
        description = response_data.get(
            "description",
            "причина не указана",
        )
        return False, f"Telegram API: {description}"

    return True, None
