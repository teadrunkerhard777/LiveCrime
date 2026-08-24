import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import Mock, patch

from config import SOURCES, TOPIC_TAGS
from core.run_lock import AlreadyRunningError, single_instance_lock
from generation.post_generator import (
    TELEGRAM_SAFE_LIMIT,
    generate_post,
    generate_tags,
)
from main import publish_selected_news
from publishing.telegram import send_telegram_post
from storage.history import add_to_history


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
        history_mock = Mock()

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [make_news_item()],
                [],
                dry_run=True,
                post_mode="single",
                send_post=send_mock,
                add_history=history_mock,
            )

        self.assertFalse(changed)
        send_mock.assert_not_called()
        history_mock.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
