import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import Mock, patch

import requests
from bs4 import BeautifulSoup

from config import SOURCES, TOPIC_TAGS
from core.run_lock import AlreadyRunningError, single_instance_lock
from generation.post_generator import (
    TELEGRAM_PHOTO_CAPTION_SAFE_LIMIT,
    TELEGRAM_SAFE_LIMIT,
    generate_photo_caption,
    generate_post,
    generate_tags,
)
from main import publish_selected_news
from publishing.telegram import send_telegram_photo, send_telegram_post
from storage.history import add_to_history


TELEGRAM_ENV = {
    "TELEGRAM_BOT_TOKEN": "test-token",
    "TELEGRAM_CHAT_ID": "test-chat",
}


def make_news_item():
    """Создаёт небольшую новость для изолированных тестов."""

    return {
        "title": "Заголовок & <проверка>",
        "url": "https://example.com/news?id=1&part=2",
        "published_at": datetime(2026, 8, 24, tzinfo=timezone.utc),
        "description": "Описание & <служебный тег>.",
        "article_text": "Первое предложение. Второе предложение.",
        "source": "Источник & партнёры",
        "matched_topics": ["уголовн", "обвин"],
    }


class PostGeneratorTests(unittest.TestCase):
    def test_html_is_escaped_and_date_is_readable(self):
        post = generate_post(make_news_item())

        self.assertIn("<b>Заголовок &amp; &lt;проверка&gt;</b>", post)
        self.assertIn("24 августа 2026", post)
        self.assertIn("📰 Источник &amp; партнёры", post)
        self.assertIn("id=1&amp;part=2", post)
        self.assertIn("#уголовноедело #обвинение", post)
        self.assertNotIn("Темы:", post)

    def test_long_article_stays_inside_telegram_limit(self):
        news_item = make_news_item()
        news_item["article_text"] = "Очень длинное предложение. " * 1000

        post = generate_post(news_item)

        self.assertLessEqual(len(post), TELEGRAM_SAFE_LIMIT)
        self.assertIn("…", post)
        self.assertIn("</a>\n\n#уголовноедело #обвинение", post)

    def test_empty_text_keeps_complete_minimal_post(self):
        news_item = make_news_item()
        news_item["article_text"] = ""
        news_item["description"] = ""

        post = generate_post(news_item)

        self.assertIn("<b>Заголовок", post)
        self.assertIn("📰", post)
        self.assertIn("Читать источник", post)

    def test_long_photo_caption_keeps_required_sections(self):
        news_item = make_news_item()
        news_item["article_text"] = "Очень длинное предложение. " * 1000

        caption = generate_photo_caption(news_item)

        self.assertLessEqual(
            len(caption),
            TELEGRAM_PHOTO_CAPTION_SAFE_LIMIT,
        )
        self.assertIn("<b>Заголовок", caption)
        self.assertIn("24 августа 2026", caption)
        self.assertIn("📰 Источник", caption)
        self.assertIn("Читать источник", caption)
        self.assertIn("#уголовноедело #обвинение", caption)
        self.assertIn("…", caption)

    def test_photo_caption_escapes_html_characters_and_quotes(self):
        news_item = make_news_item()
        news_item["title"] = 'Заголовок <тест> & "кавычки" и \'апостроф\''
        news_item["article_text"] = 'Текст <данные> & "кавычки".'

        caption = generate_photo_caption(news_item)
        soup = BeautifulSoup(caption, "html.parser")

        self.assertIn("&lt;тест&gt;", caption)
        self.assertIn("&amp;", caption)
        self.assertIn("&quot;кавычки&quot;", caption)
        self.assertIn("&#x27;апостроф&#x27;", caption)
        self.assertIsNotNone(soup.find("b"))
        self.assertIsNotNone(soup.find("a"))

    def test_multiple_topics_keep_their_order(self):
        news_item = {"matched_topics": ["покушен", "суд"]}

        self.assertEqual(
            generate_tags(news_item, TOPIC_TAGS),
            "#покушение #суд",
        )

    def test_different_topics_do_not_repeat_same_tag(self):
        news_item = {"matched_topics": ["розыск", "разыск"]}

        self.assertEqual(
            generate_tags(news_item, TOPIC_TAGS),
            "#розыск",
        )

    def test_no_more_than_four_tags_are_generated(self):
        news_item = {
            "matched_topics": [
                "убий",
                "покушен",
                "ограб",
                "похищ",
                "арест",
            ]
        }

        tags = generate_tags(news_item, TOPIC_TAGS)

        self.assertEqual(len(tags.split()), 4)
        self.assertEqual(
            tags,
            "#убийство #покушение #ограбление #похищение",
        )

    def test_empty_topics_do_not_add_tag_block(self):
        news_item = make_news_item()
        news_item["matched_topics"] = []

        post = generate_post(news_item)

        self.assertEqual(generate_tags(news_item, TOPIC_TAGS), "")
        self.assertTrue(post.endswith("</a>"))


class TelegramTests(unittest.TestCase):
    @patch("publishing.telegram.requests.post")
    def test_sender_uses_html_parse_mode(self, post_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}
        post_mock.return_value = response

        env = {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "test-chat",
        }

        with patch.dict("os.environ", env, clear=False):
            result = send_telegram_post("<b>Тест</b>")

        self.assertTrue(result)
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["parse_mode"], "HTML")
        self.assertEqual(post_mock.call_count, 1)

    @patch("publishing.telegram.requests.post")
    def test_photo_sender_uses_send_photo_with_url_and_caption(self, post_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}
        post_mock.return_value = response

        env = {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "test-chat",
        }

        with patch.dict("os.environ", env, clear=False):
            result = send_telegram_photo(
                "https://img.example/photo.jpg",
                "<b>Подпись</b>",
            )

        self.assertTrue(result)
        self.assertTrue(
            post_mock.call_args.args[0].endswith("/sendPhoto")
        )
        payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(payload["photo"], "https://img.example/photo.jpg")
        self.assertEqual(payload["caption"], "<b>Подпись</b>")
        self.assertEqual(payload["parse_mode"], "HTML")

    @patch("publishing.telegram.requests.post")
    def test_photo_sender_logs_safe_api_error_and_image_url(self, post_mock):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "ok": False,
            "description": "Bad Request: failed to get HTTP URL content",
        }
        post_mock.return_value = response

        env = {
            "TELEGRAM_BOT_TOKEN": "secret-test-token",
            "TELEGRAM_CHAT_ID": "test-chat",
        }
        output = StringIO()

        with patch.dict("os.environ", env, clear=False):
            with redirect_stdout(output):
                result = send_telegram_photo(
                    "https://img.example/broken.jpg",
                    "<b>Подпись</b>",
                )

        self.assertFalse(result)
        self.assertIn("Причина: Telegram API:", output.getvalue())
        self.assertIn(
            "Image URL: https://img.example/broken.jpg",
            output.getvalue(),
        )
        self.assertNotIn("secret-test-token", output.getvalue())


class PublishingFlowTests(unittest.TestCase):
    def test_success_sends_and_adds_history_once(self):
        news_item = make_news_item()
        history = []
        send_mock = Mock(return_value=True)
        history_mock = Mock(wraps=add_to_history)

        output = StringIO()

        with redirect_stdout(output):
            changed = publish_selected_news(
                [news_item],
                history,
                dry_run=False,
                post_mode="single",
                send_post=send_mock,
                add_history=history_mock,
            )

        self.assertTrue(changed)
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)
        self.assertIn("[TELEGRAM] Отправка 1/1", output.getvalue())

    def test_successful_photo_does_not_send_text(self):
        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"
        history = []
        send_photo_mock = Mock(return_value=True)
        send_post_mock = Mock()
        history_mock = Mock(wraps=add_to_history)

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [news_item],
                history,
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                add_history=history_mock,
            )

        self.assertTrue(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        send_post_mock.assert_not_called()
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)

    def test_failed_photo_falls_back_to_successful_text(self):
        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"
        history = []
        send_photo_mock = Mock(return_value=False)
        send_post_mock = Mock(return_value=True)
        history_mock = Mock(wraps=add_to_history)

        output = StringIO()

        with redirect_stdout(output):
            changed = publish_selected_news(
                [news_item],
                history,
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                add_history=history_mock,
            )

        self.assertTrue(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        self.assertEqual(send_post_mock.call_count, 1)
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)
        self.assertIn(
            "[TELEGRAM] sendPhoto failed after 1 attempt(s), "
            "fallback to sendMessage",
            output.getvalue(),
        )

    def test_failed_photo_and_text_do_not_change_history(self):
        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"
        send_photo_mock = Mock(return_value=False)
        send_post_mock = Mock(return_value=False)
        history_mock = Mock()

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [news_item],
                [],
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                add_history=history_mock,
            )

        self.assertFalse(changed)
        self.assertEqual(send_photo_mock.call_count, 1)
        self.assertEqual(send_post_mock.call_count, 1)
        history_mock.assert_not_called()

    def test_missing_image_uses_only_text_message(self):
        send_photo_mock = Mock()
        send_post_mock = Mock(return_value=True)
        history_mock = Mock()

        output = StringIO()

        with redirect_stdout(output):
            changed = publish_selected_news(
                [make_news_item()],
                [],
                dry_run=False,
                post_mode="single",
                send_post=send_post_mock,
                send_photo=send_photo_mock,
                add_history=history_mock,
            )

        self.assertTrue(changed)
        send_photo_mock.assert_not_called()
        self.assertEqual(send_post_mock.call_count, 1)
        self.assertEqual(history_mock.call_count, 1)
        self.assertIn(
            "[TELEGRAM] image_url not found, using sendMessage",
            output.getvalue(),
        )

    def test_failed_send_does_not_add_history(self):
        send_mock = Mock(return_value=False)
        history_mock = Mock(wraps=add_to_history)

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [make_news_item()],
                [],
                dry_run=False,
                post_mode="single",
                send_post=send_mock,
                add_history=history_mock,
            )

        self.assertFalse(changed)
        self.assertEqual(send_mock.call_count, 1)
        self.assertEqual(history_mock.call_count, 0)

    def test_dry_run_does_not_call_external_functions(self):
        send_mock = Mock()
        send_photo_mock = Mock()
        history_mock = Mock()

        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"

        output = StringIO()

        with redirect_stdout(output):
            changed = publish_selected_news(
                [news_item],
                [],
                dry_run=True,
                post_mode="single",
                send_post=send_mock,
                send_photo=send_photo_mock,
                add_history=history_mock,
            )

        self.assertFalse(changed)
        send_mock.assert_not_called()
        send_photo_mock.assert_not_called()
        history_mock.assert_not_called()
        self.assertIn("[DRY RUN] Photo URL:", output.getvalue())
        self.assertIn("[DRY RUN] Caption:", output.getvalue())

    def test_only_lenta_is_enabled(self):
        active_sources = [
            source for source in SOURCES
            if source.get("enabled", True)
        ]

        self.assertEqual(len(active_sources), 1)
        self.assertEqual(active_sources[0]["name"], "Lenta.ru")

    def test_second_process_lock_is_rejected(self):
        with single_instance_lock():
            with self.assertRaises(AlreadyRunningError):
                with single_instance_lock():
                    pass


class TelegramRetryTests(unittest.TestCase):
    @staticmethod
    def successful_response():
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}
        return response

    @patch("publishing.telegram.time.sleep")
    @patch("publishing.telegram.requests.post")
    def test_connect_timeout_then_text_success_updates_history_once(
        self,
        post_mock,
        sleep_mock,
    ):
        post_mock.side_effect = [
            requests.ConnectTimeout(),
            self.successful_response(),
        ]
        history = []
        history_mock = Mock(wraps=add_to_history)

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            with redirect_stdout(StringIO()):
                changed = publish_selected_news(
                    [make_news_item()],
                    history,
                    dry_run=False,
                    post_mode="single",
                    send_post=send_telegram_post,
                    add_history=history_mock,
                )

        self.assertTrue(changed)
        self.assertEqual(post_mock.call_count, 2)
        sleep_mock.assert_called_once_with(2)
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)

    @patch("publishing.telegram.time.sleep")
    @patch("publishing.telegram.requests.post")
    def test_http_400_is_not_retried(self, post_mock, sleep_mock):
        response = Mock()
        response.status_code = 400
        response.raise_for_status.side_effect = requests.HTTPError(
            response=response
        )
        post_mock.return_value = response

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            with redirect_stdout(StringIO()):
                result = send_telegram_post("Тест")

        self.assertFalse(result)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(post_mock.call_count, 1)
        sleep_mock.assert_not_called()

    @patch("publishing.telegram.time.sleep")
    @patch("publishing.telegram.requests.post")
    def test_photo_connect_timeout_then_success_skips_fallback(
        self,
        post_mock,
        sleep_mock,
    ):
        post_mock.side_effect = [
            requests.ConnectTimeout(),
            self.successful_response(),
        ]
        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"
        send_post_mock = Mock()
        history = []
        history_mock = Mock(wraps=add_to_history)

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            with redirect_stdout(StringIO()):
                changed = publish_selected_news(
                    [news_item],
                    history,
                    dry_run=False,
                    post_mode="single",
                    send_post=send_post_mock,
                    send_photo=send_telegram_photo,
                    add_history=history_mock,
                )

        self.assertTrue(changed)
        self.assertEqual(post_mock.call_count, 2)
        sleep_mock.assert_called_once_with(2)
        send_post_mock.assert_not_called()
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)

    @patch("publishing.telegram.time.sleep")
    @patch("publishing.telegram.requests.post")
    def test_failed_photo_attempts_fall_back_to_successful_text(
        self,
        post_mock,
        sleep_mock,
    ):
        post_mock.side_effect = [
            requests.ConnectTimeout(),
            requests.ConnectTimeout(),
            self.successful_response(),
        ]
        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"
        history = []
        history_mock = Mock(wraps=add_to_history)
        output = StringIO()

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            with redirect_stdout(output):
                changed = publish_selected_news(
                    [news_item],
                    history,
                    dry_run=False,
                    post_mode="single",
                    send_post=send_telegram_post,
                    send_photo=send_telegram_photo,
                    add_history=history_mock,
                )

        self.assertTrue(changed)
        self.assertEqual(post_mock.call_count, 3)
        sleep_mock.assert_called_once_with(2)
        self.assertEqual(history_mock.call_count, 1)
        self.assertEqual(len(history), 1)
        self.assertIn(
            "sendPhoto failed after 2 attempt(s)",
            output.getvalue(),
        )

    @patch("publishing.telegram.time.sleep")
    @patch("publishing.telegram.requests.post")
    def test_all_connect_timeout_attempts_leave_history_unchanged(
        self,
        post_mock,
        sleep_mock,
    ):
        post_mock.side_effect = [requests.ConnectTimeout()] * 4
        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"
        history_mock = Mock()

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            with redirect_stdout(StringIO()):
                changed = publish_selected_news(
                    [news_item],
                    [],
                    dry_run=False,
                    post_mode="single",
                    send_post=send_telegram_post,
                    send_photo=send_telegram_photo,
                    add_history=history_mock,
                )

        self.assertFalse(changed)
        self.assertEqual(post_mock.call_count, 4)
        self.assertEqual(sleep_mock.call_count, 2)
        history_mock.assert_not_called()

    @patch("publishing.telegram.time.sleep")
    @patch("publishing.telegram.requests.post")
    def test_read_timeout_is_not_retried_or_fallen_back(
        self,
        post_mock,
        sleep_mock,
    ):
        post_mock.side_effect = requests.ReadTimeout()
        news_item = make_news_item()
        news_item["image_url"] = "https://img.example/photo.jpg"
        send_post_mock = Mock()
        history_mock = Mock()
        output = StringIO()

        with patch.dict("os.environ", TELEGRAM_ENV, clear=False):
            with redirect_stdout(output):
                changed = publish_selected_news(
                    [news_item],
                    [],
                    dry_run=False,
                    post_mode="single",
                    send_post=send_post_mock,
                    send_photo=send_telegram_photo,
                    add_history=history_mock,
                )

        self.assertFalse(changed)
        self.assertEqual(post_mock.call_count, 1)
        sleep_mock.assert_not_called()
        send_post_mock.assert_not_called()
        history_mock.assert_not_called()
        self.assertIn("ReadTimeout", output.getvalue())
        self.assertIn("fallback disabled", output.getvalue())


if __name__ == "__main__":
    unittest.main()
