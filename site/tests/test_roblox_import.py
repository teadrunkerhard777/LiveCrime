import json
import tempfile
import unittest
from pathlib import Path

from generator.import_roblox_telegram import import_posts, parse_public_feed


FEED_HTML = """
<div class="tgme_widget_message" data-post="RobloxHubRU/501">
  <a class="tgme_widget_message_photo_wrap" style="background-image:url('https://cdn.example/one.jpg')"></a>
  <div class="tgme_widget_message_text">🔥 Новинка<br><br>Текст поста #Roblox</div>
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

    def test_import_is_idempotent_and_skips_non_photo_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            content_path = Path(directory)

            first = import_posts(content_path, feed_html=FEED_HTML)
            second = import_posts(content_path, feed_html=FEED_HTML)

            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            payload = json.loads(first[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["message_id"], "501")


if __name__ == "__main__":
    unittest.main()
