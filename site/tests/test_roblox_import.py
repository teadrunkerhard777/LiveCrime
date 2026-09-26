import json
import tempfile
import unittest
from pathlib import Path

from generator.import_roblox_telegram import import_posts, parse_public_feed


SITE_ROOT = Path(__file__).resolve().parents[1]
POST_CARD = (SITE_ROOT / "src/components/TelegramPostCard.astro").read_text(encoding="utf-8")

FEED_HTML = """
<div class="tgme_widget_message" data-post="RobloxHubRU/501">
  <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.example/one.jpg')"></a>
  <div class="tgme_widget_message_text">🔥 Новинка<br><br>Текст поста #Roblox<br><br>🔗 <a href="https://example.com/news/501">Читать источник</a></div>
  <time datetime="2026-09-23T10:15:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="RobloxHubRU/502">
  <div class="tgme_widget_message_text">Пост без изображения</div>
  <time datetime="2026-09-23T11:15:00+00:00"></time>
</div>
<div class="tgme_widget_message" data-post="OtherChannel/503">
  <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.example/other.jpg')"></a>
  <div class="tgme_widget_message_text">Чужой пост</div>
  <time datetime="2026-09-23T12:15:00+00:00"></time>
</div>
"""


class RobloxTelegramImportTests(unittest.TestCase):
    def test_parser_keeps_text_photo_date_and_message_link(self):
        posts = parse_public_feed(FEED_HTML)

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["message_id"], "501")
        self.assertEqual(posts[0]["text"], "🔥 Новинка\n\nТекст поста #Roblox")
        self.assertEqual(posts[0]["image_url"], "https://cdn.example/one.jpg")
        self.assertEqual(posts[0]["telegram_url"], "https://t.me/RobloxHubRU/501")
        self.assertEqual(posts[0]["source_url"], "https://example.com/news/501")
        self.assertNotIn("Читать источник", posts[0]["text"])

    def test_import_is_idempotent_and_skips_non_photo_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            content_path = Path(directory)

            first = import_posts(content_path, feed_html=FEED_HTML)
            second = import_posts(content_path, feed_html=FEED_HTML)

            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            payload = json.loads(first[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["message_id"], "501")
            self.assertEqual(payload["source_url"], "https://example.com/news/501")

    def test_existing_post_is_updated_when_source_link_appears(self):
        without_source = FEED_HTML.replace(
            '<br><br>🔗 <a href="https://example.com/news/501">Читать источник</a>',
            "",
        )
        with tempfile.TemporaryDirectory() as directory:
            content_path = Path(directory)
            first = import_posts(content_path, feed_html=without_source)
            second = import_posts(content_path, feed_html=FEED_HTML)

            self.assertEqual(len(first), 1)
            self.assertEqual(len(second), 1)
            payload = json.loads(second[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["source_url"], "https://example.com/news/501")

    def test_short_source_label_is_also_extracted(self):
        short_label_html = FEED_HTML.replace("Читать источник", "Источник")

        posts = parse_public_feed(short_label_html)

        self.assertEqual(posts[0]["source_url"], "https://example.com/news/501")
        self.assertNotIn("Источник", posts[0]["text"])

    def test_post_card_renders_source_as_a_real_link(self):
        self.assertIn("post.data.source_url", POST_CARD)
        self.assertIn("href={post.data.source_url}", POST_CARD)
        self.assertIn("Читать источник ↗", POST_CARD)

    def test_same_parser_supports_the_crime_channel(self):
        crime_html = FEED_HTML.replace("RobloxHubRU", "truecrime_news")

        posts = parse_public_feed(crime_html, "truecrime_news")

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["telegram_url"], "https://t.me/truecrime_news/501")


if __name__ == "__main__":
    unittest.main()
