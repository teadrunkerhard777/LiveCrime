import os
import time
from dataclasses import dataclass

import requests
from dotenv import load_dotenv


# Загружаем переменные из локального .env.
# Существующие переменные окружения при этом не перезаписываются.
load_dotenv()


TELEGRAM_MAX_ATTEMPTS = 2
TELEGRAM_RETRY_DELAY_SECONDS = 2


@dataclass(frozen=True)
class TelegramSendResult:
    """Хранит подтверждённый результат и неопределённый сетевой исход."""

    success: bool
    error_reason: str | None = None
    attempts: int = 0
    uncertain: bool = False

    def __bool__(self):
        return self.success


def send_telegram_post(text):
    """
    Отправляет один текстовый пост через Telegram Bot API.

    Результат считается truthy только после подтверждения Telegram.
    При ошибке возвращается безопасная причина без секретов.
    """

    result = _send_telegram_request(
        "sendMessage",
        {
            "text": text,
            "parse_mode": "HTML",
        },
    )

    if not result:
        print(f"Ошибка Telegram: {result.error_reason}")

    return result


def send_telegram_photo(image_url, caption):
    """Отправляет картинку по URL и caption как одно Telegram-сообщение."""

    if not image_url:
        print("Ошибка Telegram: URL изображения не указан.")
        return TelegramSendResult(
            success=False,
            error_reason="URL изображения не указан",
        )

    # Telegram сам получает изображение: локальный файл не создаётся.
    result = _send_telegram_request(
        "sendPhoto",
        {
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML",
        },
    )

    if not result:
        # URL безопасно показывать в Actions: токена в нём нет.
        print(f"Причина: {result.error_reason}")
        print(f"Image URL: {image_url}")

    return result


def _send_telegram_request(method, payload):
    """Отправляет запрос с безопасным retry до соединения с Telegram."""

    # Токен и chat ID читаем только из окружения.
    # Секреты не должны храниться в исходном коде.
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Без обязательных настроек запрос всё равно не сможет пройти.
    if not bot_token or not chat_id:
        return TelegramSendResult(
            success=False,
            error_reason=(
                "не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID"
            ),
        )

    api_url = f"https://api.telegram.org/bot{bot_token}/{method}"

    # Telegram разберёт только минимальные теги <b> и <a>,
    # которые формирует и безопасно экранирует post_generator.py.
    request_payload = {"chat_id": chat_id, **payload}

    for attempt in range(1, TELEGRAM_MAX_ATTEMPTS + 1):
        print(
            f"[TELEGRAM] {method} attempt "
            f"{attempt}/{TELEGRAM_MAX_ATTEMPTS}"
        )

        try:
            # timeout не позволяет зависнуть при проблемах с сетью.
            response = requests.post(
                api_url,
                json=request_payload,
                timeout=15,
            )

            # HTTP-ответ означает, что retry уже небезопасен или бесполезен.
            response.raise_for_status()

        except requests.ConnectTimeout:
            # ConnectTimeout возникает до установленного соединения,
            # поэтому повтор не создаст второе Telegram-сообщение.
            if attempt < TELEGRAM_MAX_ATTEMPTS:
                print(
                    "[TELEGRAM] ConnectTimeout, retry через "
                    f"{TELEGRAM_RETRY_DELAY_SECONDS} сек."
                )
                time.sleep(TELEGRAM_RETRY_DELAY_SECONDS)
                continue

            return TelegramSendResult(
                success=False,
                error_reason="сетевая ошибка ConnectTimeout",
                attempts=attempt,
            )

        except requests.ReadTimeout:
            # Telegram мог принять запрос до разрыва ожидания ответа.
            # Повтор или fallback здесь способен создать дубль.
            print(
                "[TELEGRAM] ReadTimeout: результат неизвестен, "
                "автоматический retry отключён"
            )
            return TelegramSendResult(
                success=False,
                error_reason="сетевая ошибка ReadTimeout",
                attempts=attempt,
                uncertain=True,
            )

        except requests.ConnectionError as error:
            # Общий ConnectionError не гарантирует, что запрос не был принят.
            print(
                "[TELEGRAM] ConnectionError: результат неизвестен, "
                "автоматический retry отключён"
            )
            return TelegramSendResult(
                success=False,
                error_reason=f"сетевая ошибка {type(error).__name__}",
                attempts=attempt,
                uncertain=True,
            )

        except requests.HTTPError as error:
            status_code = (
                error.response.status_code
                if error.response is not None
                else "неизвестен"
            )
            return TelegramSendResult(
                success=False,
                error_reason=f"сервер вернул HTTP-статус {status_code}",
                attempts=attempt,
            )

        except requests.RequestException as error:
            # Не печатаем URL запроса, потому что внутри него находится токен.
            return TelegramSendResult(
                success=False,
                error_reason=f"сетевая ошибка {type(error).__name__}",
                attempts=attempt,
            )

        break

    try:
        # Telegram всегда возвращает JSON с логическим полем ok.
        response_data = response.json()

    except requests.exceptions.JSONDecodeError:
        return TelegramSendResult(
            success=False,
            error_reason="сервер вернул некорректный JSON",
            attempts=attempt,
        )

    # Защищаемся от неожиданного JSON-формата без поля ok.
    if not isinstance(response_data, dict):
        return TelegramSendResult(
            success=False,
            error_reason="сервер вернул неожиданный формат ответа",
            attempts=attempt,
        )

    # Даже при HTTP 200 Telegram может сообщить об ошибке через ok=False.
    if response_data.get("ok") is not True:
        description = response_data.get(
            "description",
            "причина не указана",
        )
        return TelegramSendResult(
            success=False,
            error_reason=f"Telegram API: {description}",
            attempts=attempt,
        )

    return TelegramSendResult(
        success=True,
        attempts=attempt,
    )
