import os
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path

import requests
from dotenv import load_dotenv


# Загружаем переменные из локального .env.
# Существующие переменные окружения при этом не перезаписываются.
load_dotenv()


TELEGRAM_MAX_ATTEMPTS = 2
TELEGRAM_RETRY_DELAY_SECONDS = 2
TELEGRAM_CONNECT_TIMEOUT_SECONDS = 10
TELEGRAM_READ_TIMEOUT_SECONDS = 30

# Telegram принимает фотографии размером до 10 МБ.
# Такой же предел не даёт runner скачать неожиданно большой файл.
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Картинка скачивается с заголовком обычного браузера.
IMAGE_DOWNLOAD_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)

# Только эти ответы означают, что Telegram не смог получить remote URL.
# Другие ошибки Bot API не должны запускать скачивание файла.
REMOTE_IMAGE_FETCH_ERROR_MARKERS = (
    "failed to get http url content",
    "wrong type of the web page content",
)

IMAGE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@dataclass(frozen=True)
class TelegramSendResult:
    """Хранит подтверждённый результат и неопределённый сетевой исход."""

    success: bool
    error_reason: str | None = None
    attempts: int = 0
    uncertain: bool = False
    remote_fetch_failed: bool = False

    def __bool__(self):
        return self.success


@dataclass(frozen=True)
class TemporaryImage:
    """Описывает скачанный файл без хранения binary data в памяти."""

    path: Path
    mime_type: str
    size_bytes: int


class ImageDownloadError(Exception):
    """Ожидаемая ошибка получения непригодной картинки."""


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


def send_telegram_photo(photo, caption, filename=None, mime_type=None):
    """Отправляет remote URL или открытый файл одним photo-сообщением."""

    if not photo:
        print("Ошибка Telegram: изображение не указано.")
        return TelegramSendResult(
            success=False,
            error_reason="изображение не указано",
        )

    payload = {
        "caption": caption,
        "parse_mode": "HTML",
    }
    files = None
    image_url = photo if isinstance(photo, str) else None

    if image_url:
        # В первом варианте Telegram самостоятельно получает remote URL.
        payload["photo"] = image_url
    else:
        # Открытый файл передаётся как multipart/form-data.
        safe_filename = filename or "livecrime-photo.jpg"
        safe_mime_type = mime_type or "application/octet-stream"
        files = {
            "photo": (safe_filename, photo, safe_mime_type),
        }

    result = _send_telegram_request("sendPhoto", payload, files=files)

    # Отдельный признак позволяет main.py включить file fallback
    # только для подтверждённой ошибки загрузки remote URL.
    if image_url and _is_remote_image_fetch_error(result.error_reason):
        result = replace(result, remote_fetch_failed=True)

    if not result:
        # Binary data и Telegram token никогда не попадают в лог.
        print(f"Причина: {result.error_reason}")

        if image_url:
            # URL картинки безопасно показывать в Actions.
            print(f"Image URL: {image_url}")

    return result


def download_image_temp(image_url):
    """Потоково скачивает проверенную картинку во временный каталог ОС."""

    response = None
    temp_path = None
    download_completed = False

    try:
        response = requests.get(
            image_url,
            headers={"User-Agent": IMAGE_DOWNLOAD_USER_AGENT},
            timeout=(
                TELEGRAM_CONNECT_TIMEOUT_SECONDS,
                TELEGRAM_READ_TIMEOUT_SECONDS,
            ),
            stream=True,
        )
        response.raise_for_status()

        # Параметры вроде charset не являются частью MIME-типа.
        mime_type = response.headers.get("Content-Type", "")
        mime_type = mime_type.split(";", 1)[0].strip().casefold()

        if not mime_type.startswith("image/"):
            raise ImageDownloadError(
                f"неподходящий Content-Type: {mime_type or 'не указан'}"
            )

        content_length = response.headers.get("Content-Length")

        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = 0

            if declared_size > MAX_IMAGE_SIZE_BYTES:
                raise ImageDownloadError(
                    "изображение превышает лимит 10 МБ"
                )

        # Расширение определяется по MIME, а не по ненадёжному URL.
        suffix = IMAGE_SUFFIXES.get(mime_type, ".img")

        with tempfile.NamedTemporaryFile(
            prefix="livecrime-photo-",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            downloaded_size = 0

            # Небольшие chunks не держат весь файл в памяти runner-а.
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue

                downloaded_size += len(chunk)

                if downloaded_size > MAX_IMAGE_SIZE_BYTES:
                    raise ImageDownloadError(
                        "изображение превышает лимит 10 МБ"
                    )

                temp_file.write(chunk)

        if downloaded_size == 0:
            raise ImageDownloadError("сервер вернул пустой файл")

        temporary_image = TemporaryImage(
            path=temp_path,
            mime_type=mime_type,
            size_bytes=downloaded_size,
        )
        download_completed = True
        return temporary_image

    except requests.HTTPError as error:
        status_code = (
            error.response.status_code
            if error.response is not None
            else "неизвестен"
        )
        raise ImageDownloadError(f"HTTP {status_code}") from error

    except requests.RequestException as error:
        raise ImageDownloadError(
            f"сетевая ошибка {type(error).__name__}"
        ) from error

    finally:
        if response is not None:
            response.close()

        # При любой ошибке частично записанный файл сразу удаляется.
        if (
            temp_path is not None
            and not download_completed
            and temp_path.exists()
        ):
            temp_path.unlink()


def _send_telegram_request(method, payload, files=None):
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
    log_prefix = "[PHOTO]" if method == "sendPhoto" else "[TELEGRAM]"

    for attempt in range(1, TELEGRAM_MAX_ATTEMPTS + 1):
        print(
            f"{log_prefix} {method} attempt "
            f"{attempt}/{TELEGRAM_MAX_ATTEMPTS}"
        )

        try:
            # После ConnectTimeout multipart-файл читается заново с начала.
            if files:
                for file_data in files.values():
                    file_data[1].seek(0)

            # Telegram иногда дольше забирает remote image URL.
            # Раздельный read timeout даёт sendPhoto время, не меняя
            # безопасную стратегию для неопределённого результата.
            request_arguments = {
                "timeout": (
                    TELEGRAM_CONNECT_TIMEOUT_SECONDS,
                    TELEGRAM_READ_TIMEOUT_SECONDS,
                ),
            }

            if files:
                request_arguments["data"] = request_payload
                request_arguments["files"] = files
            else:
                request_arguments["json"] = request_payload

            response = requests.post(api_url, **request_arguments)

            # HTTP-ответ означает, что retry уже небезопасен или бесполезен.
            response.raise_for_status()

        except requests.ConnectTimeout:
            # ConnectTimeout возникает до установленного соединения,
            # поэтому повтор не создаст второе Telegram-сообщение.
            if attempt < TELEGRAM_MAX_ATTEMPTS:
                print(
                    f"{log_prefix} ConnectTimeout, retry через "
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
                f"{log_prefix} result: ReadTimeout; "
                "publication status unknown, "
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
                f"{log_prefix} result: ConnectionError; "
                "publication status unknown, "
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
            # Telegram обычно присылает полезное поле description даже с 4xx.
            # Показываем только его: URL API с токеном никогда не логируется.
            api_description = _read_api_error_description(error.response)
            reason = f"сервер вернул HTTP-статус {status_code}"

            if api_description:
                reason = f"{reason}: {api_description}"

            return TelegramSendResult(
                success=False,
                error_reason=reason,
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


def _read_api_error_description(response):
    """Безопасно читает короткое описание ошибки Telegram из JSON."""

    if response is None:
        return None

    try:
        response_data = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return None

    if not isinstance(response_data, dict):
        return None

    description = response_data.get("description")

    if not isinstance(description, str):
        return None

    # Ограничение защищает Actions logs от неожиданно большого ответа.
    return description.strip()[:300] or None


def _is_remote_image_fetch_error(error_reason):
    """Распознаёт только ошибки получения картинки по remote URL."""

    if not error_reason:
        return False

    normalized_reason = error_reason.casefold()

    return any(
        marker in normalized_reason
        for marker in REMOTE_IMAGE_FETCH_ERROR_MARKERS
    )
