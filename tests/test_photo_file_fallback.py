import tempfile
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from main import publish_selected_news
from publishing.telegram import (
    MAX_IMAGE_SIZE_BYTES,
    ImageDownloadError,
    TelegramSendResult,
    TemporaryImage,
    download_image_temp,
    send_telegram_photo,
)
from storage.history import add_to_history


TELEGRAM_ENV = {
    "TELEGRAM_BOT_TOKEN": "test-token",
    "TELEGRAM_CHAT_ID": "test-chat",
}


def make_news_item():
    """Создаёт новость с картинкой для проверки photo flow."""

    return {
        "title": "Тестовая новость",
        "url": "https://example.com/news/1",
        "published_at": None,
        "description": "Описание новости.",
        "article_text": "Основной текст новости.",
        "source": "Тестовый источник",
        "matched_topics": ["убий"],
        "image_url": "https://img.example/photo.jpg",
    }


def remote_fetch_failure():
    """Имитирует подтверждённую ошибку получения remote URL."""

    return TelegramSendResult(
        success=False,
        error_reason="Bad Request: failed to get HTTP URL content",
        attempts=1,
        remote_fetch_failed=True,
    )


def uncertain_timeout():
    """Имитирует ReadTimeout с неизвестным статусом доставки."""

    return TelegramSendResult(
        success=False,
        error_reason="сетевая ошибка ReadTimeout",
        attempts=1,
        uncertain=True,
    )


def create_temporary_image():
    """Создаёт реальный temp-файл, удаление которого можно проверить."""

    temp_file = tempfile.NamedTemporaryFile(
        prefix="livecrime-test-photo-",
        suffix=".jpg",
        delete=False,
    )
    temp_file.write(b"test-image")
    temp_file.close()

    return TemporaryImage(
        path=Path(temp_file.name),
        mime_type="image/jpeg",
        size_bytes=10,
    )


class PhotoFileFallbackFlowTests(unittest.TestCase):
    def test_remote_url_success_stops_the_chain(self):
        history = []
        history_mock = Mock(wraps=add_to_history)
        send_photo_mock = Mock(return_value=TelegramSendResult(True))
        download_mock = Mock()
        send_post_mock = Mock()

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [make_news_item()],
                history,
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                download_image=download_mock,
                add_history=history_mock,
            )

        self.assertTrue(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        download_mock.assert_not_called()
        send_post_mock.assert_not_called()
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)

    def test_remote_fetch_failure_uses_file_and_stops_after_success(self):
        temporary_image = create_temporary_image()
        history = []
        history_mock = Mock(wraps=add_to_history)
        send_photo_mock = Mock(
            side_effect=[remote_fetch_failure(), TelegramSendResult(True)]
        )
        download_mock = Mock(return_value=temporary_image)
        send_post_mock = Mock()

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [make_news_item()],
                history,
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                download_image=download_mock,
                add_history=history_mock,
            )

        self.assertTrue(changed)
        self.assertEqual(send_photo_mock.call_count, 2)
        download_mock.assert_called_once()
        send_post_mock.assert_not_called()
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)
        self.assertFalse(temporary_image.path.exists())

    def test_download_failure_uses_text_fallback(self):
        history = []
        history_mock = Mock(wraps=add_to_history)
        send_photo_mock = Mock(return_value=remote_fetch_failure())
        download_mock = Mock(
            side_effect=ImageDownloadError("HTTP 403")
        )
        send_post_mock = Mock(return_value=TelegramSendResult(True))
        output = StringIO()

        with redirect_stdout(output):
            changed = publish_selected_news(
                [make_news_item()],
                history,
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                download_image=download_mock,
                add_history=history_mock,
            )

        self.assertTrue(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        self.assertEqual(send_post_mock.call_count, 1)
        self.assertEqual(history_mock.call_count, 1)
        self.assertIn("temporary download failed: HTTP 403", output.getvalue())

    def test_confirmed_file_failure_uses_text_fallback(self):
        temporary_image = create_temporary_image()
        history = []
        history_mock = Mock(wraps=add_to_history)
        file_failure = TelegramSendResult(
            False,
            error_reason="Telegram API: Bad Request: invalid photo",
            attempts=1,
        )
        send_photo_mock = Mock(
            side_effect=[remote_fetch_failure(), file_failure]
        )
        send_post_mock = Mock(return_value=TelegramSendResult(True))

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [make_news_item()],
                history,
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                download_image=Mock(return_value=temporary_image),
                add_history=history_mock,
            )

        self.assertTrue(changed)
        self.assertEqual(send_photo_mock.call_count, 2)
        self.assertEqual(send_post_mock.call_count, 1)
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)
        self.assertFalse(temporary_image.path.exists())

    def test_remote_read_timeout_stops_without_fallback(self):
        send_photo_mock = Mock(return_value=uncertain_timeout())
        download_mock = Mock()
        send_post_mock = Mock()
        history_mock = Mock()

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [make_news_item()],
                [],
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                download_image=download_mock,
                add_history=history_mock,
            )

        self.assertFalse(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        download_mock.assert_not_called()
        send_post_mock.assert_not_called()
        history_mock.assert_not_called()

    def test_file_read_timeout_stops_without_text_fallback(self):
        temporary_image = create_temporary_image()
        send_photo_mock = Mock(
            side_effect=[remote_fetch_failure(), uncertain_timeout()]
        )
        send_post_mock = Mock()
        history_mock = Mock()

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [make_news_item()],
                [],
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                download_image=Mock(return_value=temporary_image),
                add_history=history_mock,
            )

        self.assertFalse(changed)
        send_post_mock.assert_not_called()
        history_mock.assert_not_called()
        self.assertFalse(temporary_image.path.exists())

    def test_temp_file_is_removed_when_file_sender_raises(self):
        temporary_image = create_temporary_image()
        send_photo_mock = Mock(
            side_effect=[remote_fetch_failure(), RuntimeError("test error")]
        )

        with self.assertRaises(RuntimeError):
            with redirect_stdout(StringIO()):
                publish_selected_news(
                    [make_news_item()],
                    [],
                    dry_run=False,
                    post_mode="single",
                    send_post=Mock(),
                    send_photo=send_photo_mock,
                    download_image=Mock(return_value=temporary_image),
                    add_history=Mock(),
                )

        self.assertFalse(temporary_image.path.exists())


class ImageDownloadTests(unittest.TestCase):
    @patch("publishing.telegram.requests.get")
    def test_valid_image_is_streamed_to_temporary_file(self, get_mock):
        response = Mock()
        response.headers = {
            "Content-Type": "image/jpeg; charset=binary",
            "Content-Length": "10",
        }
        response.raise_for_status.return_value = None
        response.iter_content.return_value = [b"test-", b"image"]
        get_mock.return_value = response

        temporary_image = download_image_temp(
            "https://img.example/photo-without-extension"
        )

        try:
            self.assertEqual(temporary_image.mime_type, "image/jpeg")
            self.assertEqual(temporary_image.size_bytes, 10)
            self.assertEqual(temporary_image.path.suffix, ".jpg")
            self.assertEqual(temporary_image.path.read_bytes(), b"test-image")
            self.assertTrue(get_mock.call_args.kwargs["stream"])
            self.assertIn(
                "Mozilla/5.0",
                get_mock.call_args.kwargs["headers"]["User-Agent"],
            )
            self.assertEqual(get_mock.call_args.kwargs["timeout"], (10, 30))
        finally:
            temporary_image.path.unlink(missing_ok=True)

    @patch("publishing.telegram.requests.get")
    def test_invalid_mime_is_rejected(self, get_mock):
        response = Mock()
        response.headers = {"Content-Type": "text/html"}
        response.raise_for_status.return_value = None
        get_mock.return_value = response

        with self.assertRaisesRegex(ImageDownloadError, "Content-Type"):
            download_image_temp("https://img.example/not-image")

        response.close.assert_called_once()

    @patch("publishing.telegram.requests.get")
    def test_declared_oversized_image_is_rejected(self, get_mock):
        response = Mock()
        response.headers = {
            "Content-Type": "image/jpeg",
            "Content-Length": str(MAX_IMAGE_SIZE_BYTES + 1),
        }
        response.raise_for_status.return_value = None
        get_mock.return_value = response

        with self.assertRaisesRegex(ImageDownloadError, "лимит 10 МБ"):
            download_image_temp("https://img.example/huge.jpg")

        response.iter_content.assert_not_called()
        response.close.assert_called_once()

    @patch("publishing.telegram.requests.get")
    def test_streamed_oversized_image_removes_partial_temp_file(
        self,
        get_mock,
    ):
        response = Mock()
        response.headers = {"Content-Type": "image/jpeg"}
        response.raise_for_status.return_value = None
        response.iter_content.return_value = [
            b"x" * MAX_IMAGE_SIZE_BYTES,
            b"y",
        ]
        get_mock.return_value = response

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("publishing.telegram.tempfile.tempdir", temp_dir):
                with self.assertRaisesRegex(
                    ImageDownloadError,
                    "лимит 10 МБ",
                ):
                    download_image_temp("https://img.example/huge.jpg")

            self.assertEqual(list(Path(temp_dir).iterdir()), [])

    @patch("publishing.telegram.requests.post")
    def test_file_sender_uses_multipart_form_data(self, post_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}
        post_mock.return_value = response
        image_file = BytesIO(b"test-image")

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            result = send_telegram_photo(
                image_file,
                "<b>Подпись</b>",
                filename="photo.jpg",
                mime_type="image/jpeg",
            )

        self.assertTrue(result)
        self.assertNotIn("json", post_mock.call_args.kwargs)
        self.assertEqual(
            post_mock.call_args.kwargs["data"]["parse_mode"],
            "HTML",
        )
        upload = post_mock.call_args.kwargs["files"]["photo"]
        self.assertEqual(upload[0], "photo.jpg")
        self.assertIs(upload[1], image_file)
        self.assertEqual(upload[2], "image/jpeg")

    @patch("publishing.telegram.requests.post")
    def test_file_sender_read_timeout_is_uncertain_and_not_retried(
        self,
        post_mock,
    ):
        post_mock.side_effect = requests.ReadTimeout()
        image_file = BytesIO(b"test-image")

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            with redirect_stdout(StringIO()):
                result = send_telegram_photo(
                    image_file,
                    "caption",
                    filename="photo.jpg",
                    mime_type="image/jpeg",
                )

        self.assertFalse(result)
        self.assertTrue(result.uncertain)
        self.assertEqual(post_mock.call_count, 1)

    @patch("publishing.telegram.requests.post")
    def test_only_remote_fetch_error_sets_file_fallback_flag(self, post_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ok": False,
            "description": "Bad Request: chat not found",
        }
        post_mock.return_value = response

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            result = send_telegram_photo(
                "https://img.example/photo.jpg",
                "caption",
            )

        self.assertFalse(result.remote_fetch_failed)

    @patch("publishing.telegram.requests.post")
    def test_remote_fetch_error_sets_file_fallback_flag(self, post_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ok": False,
            "description": "Bad Request: failed to get HTTP URL content",
        }
        post_mock.return_value = response

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            result = send_telegram_photo(
                "https://img.example/photo.jpg",
                "caption",
            )

        self.assertTrue(result.remote_fetch_failed)


if __name__ == "__main__":
    unittest.main()
