import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from generation.post_generator import generate_photo_caption
from main import is_usable_article_image, publish_selected_news
from publishing.telegram import TelegramSendResult


def make_news_item(image_url=None):
    """Создаёт одну новость для изолированной проверки выбора картинки."""

    return {
        "title": "Тестовая новость",
        "url": "https://example.com/news/1",
        "published_at": None,
        "description": "Описание новости.",
        "article_text": "Основной текст новости.",
        "source": "Тестовый источник",
        "matched_topics": ["убий"],
        "image_url": image_url,
    }


def uncertain_timeout():
    """Имитирует исход, при котором Telegram мог принять сообщение."""

    return TelegramSendResult(
        success=False,
        error_reason="сетевая ошибка ReadTimeout",
        attempts=1,
        uncertain=True,
    )


class ArticleImageUsabilityTests(unittest.TestCase):
    def test_missing_image_is_not_usable(self):
        self.assertFalse(is_usable_article_image(None))

    def test_agn_social_logo_is_not_usable(self):
        self.assertFalse(
            is_usable_article_image(
                "https://www.mskagency.ru/i/social_logo_700.png"
            )
        )

    def test_placeholder_image_is_not_usable(self):
        self.assertFalse(
            is_usable_article_image(
                "https://img.example/news/placeholder-1200.png"
            )
        )

    def test_normal_article_photo_is_usable(self):
        self.assertTrue(
            is_usable_article_image(
                "https://img.example/news/crime-scene-1200.jpg"
            )
        )


class FallbackBannerFlowTests(unittest.TestCase):
    def run_with_banner(self, news_item, send_photo, **kwargs):
        """Создаёт локальный test banner только на время одного теста."""

        with tempfile.TemporaryDirectory() as temp_dir:
            banner_path = Path(temp_dir) / "livecrime_fallback_banner.png"
            banner_path.write_bytes(b"test-png")

            with redirect_stdout(StringIO()) as output:
                changed = publish_selected_news(
                    [news_item],
                    [],
                    dry_run=False,
                    post_mode="single",
                    send_post=kwargs.get("send_post", Mock()),
                    send_photo=send_photo,
                    add_history=kwargs.get("add_history", Mock()),
                    fallback_banner_path=banner_path,
                )

            return changed, output.getvalue(), banner_path

    def test_missing_image_sends_banner_as_multipart_with_caption(self):
        news_item = make_news_item()
        send_photo_mock = Mock(return_value=TelegramSendResult(True))
        send_post_mock = Mock()
        history_mock = Mock()

        changed, output, banner_path = self.run_with_banner(
            news_item,
            send_photo_mock,
            send_post=send_post_mock,
            add_history=history_mock,
        )

        self.assertTrue(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        photo_argument = send_photo_mock.call_args.args[0]
        self.assertFalse(isinstance(photo_argument, str))
        self.assertEqual(
            send_photo_mock.call_args.args[1],
            generate_photo_caption(news_item),
        )
        self.assertEqual(
            send_photo_mock.call_args.kwargs,
            {
                "filename": banner_path.name,
                "mime_type": "image/png",
            },
        )
        send_post_mock.assert_not_called()
        history_mock.assert_called_once()
        self.assertIn("fallback banner success", output)

    def test_service_image_selects_banner_instead_of_remote_url(self):
        news_item = make_news_item(
            "https://www.mskagency.ru/i/social_logo_700.png"
        )
        send_photo_mock = Mock(return_value=TelegramSendResult(True))

        self.run_with_banner(news_item, send_photo_mock)

        self.assertEqual(send_photo_mock.call_count, 1)
        self.assertFalse(isinstance(send_photo_mock.call_args.args[0], str))

    def test_normal_image_success_does_not_send_banner_or_text(self):
        news_item = make_news_item(
            "https://img.example/news/article-photo.jpg"
        )
        send_photo_mock = Mock(return_value=TelegramSendResult(True))
        send_post_mock = Mock()

        self.run_with_banner(
            news_item,
            send_photo_mock,
            send_post=send_post_mock,
        )

        send_photo_mock.assert_called_once_with(
            news_item["image_url"],
            generate_photo_caption(news_item),
        )
        send_post_mock.assert_not_called()

    def test_confirmed_normal_photo_failure_can_use_banner(self):
        news_item = make_news_item(
            "https://img.example/news/article-photo.jpg"
        )
        confirmed_failure = TelegramSendResult(
            False,
            error_reason="Telegram API: invalid photo",
            attempts=1,
        )
        send_photo_mock = Mock(
            side_effect=[confirmed_failure, TelegramSendResult(True)]
        )
        send_post_mock = Mock()

        self.run_with_banner(
            news_item,
            send_photo_mock,
            send_post=send_post_mock,
        )

        self.assertEqual(send_photo_mock.call_count, 2)
        self.assertIsInstance(send_photo_mock.call_args_list[0].args[0], str)
        self.assertFalse(
            isinstance(send_photo_mock.call_args_list[1].args[0], str)
        )
        send_post_mock.assert_not_called()

    def test_missing_banner_falls_back_to_text(self):
        send_photo_mock = Mock()
        send_post_mock = Mock(return_value=TelegramSendResult(True))

        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.png"
            with redirect_stdout(StringIO()) as output:
                changed = publish_selected_news(
                    [make_news_item()],
                    [],
                    dry_run=False,
                    post_mode="single",
                    send_post=send_post_mock,
                    send_photo=send_photo_mock,
                    add_history=Mock(),
                    fallback_banner_path=missing_path,
                )

        self.assertTrue(changed)
        send_photo_mock.assert_not_called()
        send_post_mock.assert_called_once()
        self.assertIn("fallback banner not found", output.getvalue())

    def test_confirmed_banner_send_failure_falls_back_to_text(self):
        banner_failure = TelegramSendResult(
            False,
            error_reason="Telegram API: invalid photo",
            attempts=1,
        )
        send_photo_mock = Mock(return_value=banner_failure)
        send_post_mock = Mock(return_value=TelegramSendResult(True))

        changed, output, _ = self.run_with_banner(
            make_news_item(),
            send_photo_mock,
            send_post=send_post_mock,
        )

        self.assertTrue(changed)
        send_photo_mock.assert_called_once()
        send_post_mock.assert_called_once()
        self.assertIn("fallback banner failed", output)

    def test_banner_read_timeout_does_not_send_text(self):
        send_photo_mock = Mock(return_value=uncertain_timeout())
        send_post_mock = Mock()

        changed, output, _ = self.run_with_banner(
            make_news_item(),
            send_photo_mock,
            send_post=send_post_mock,
        )

        self.assertFalse(changed)
        send_photo_mock.assert_called_once()
        send_post_mock.assert_not_called()
        self.assertIn("no sendMessage fallback", output)

    def test_unreadable_banner_falls_back_to_text(self):
        send_photo_mock = Mock()
        send_post_mock = Mock(return_value=TelegramSendResult(True))

        with tempfile.TemporaryDirectory() as temp_dir:
            # Попытка открыть каталог как PNG надёжно создаёт OSError.
            with redirect_stdout(StringIO()) as output:
                changed = publish_selected_news(
                    [make_news_item()],
                    [],
                    dry_run=False,
                    post_mode="single",
                    send_post=send_post_mock,
                    send_photo=send_photo_mock,
                    add_history=Mock(),
                    fallback_banner_path=Path(temp_dir),
                )

        self.assertTrue(changed)
        send_photo_mock.assert_not_called()
        send_post_mock.assert_called_once()
        self.assertIn("fallback banner cannot be read", output.getvalue())

    def test_normal_photo_read_timeout_does_not_try_banner_or_text(self):
        news_item = make_news_item(
            "https://img.example/news/article-photo.jpg"
        )
        send_photo_mock = Mock(return_value=uncertain_timeout())
        send_post_mock = Mock()

        changed, output, _ = self.run_with_banner(
            news_item,
            send_photo_mock,
            send_post=send_post_mock,
        )

        self.assertFalse(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        send_post_mock.assert_not_called()
        self.assertNotIn("trying local fallback banner", output)
        self.assertIn("no retry or fallback", output)

    def test_dry_run_with_banner_never_calls_telegram(self):
        send_photo_mock = Mock()
        send_post_mock = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            banner_path = Path(temp_dir) / "livecrime_fallback_banner.png"
            banner_path.write_bytes(b"test-png")
            with redirect_stdout(StringIO()) as output:
                changed = publish_selected_news(
                    [make_news_item()],
                    [],
                    dry_run=True,
                    post_mode="single",
                    send_post=send_post_mock,
                    send_photo=send_photo_mock,
                    add_history=Mock(),
                    fallback_banner_path=banner_path,
                )

        self.assertFalse(changed)
        send_photo_mock.assert_not_called()
        send_post_mock.assert_not_called()
        self.assertIn("Selected image source: fallback banner", output.getvalue())


if __name__ == "__main__":
    unittest.main()
