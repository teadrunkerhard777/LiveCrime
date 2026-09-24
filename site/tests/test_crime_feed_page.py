import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
PAGE = (SITE_ROOT / "src/pages/crime/index.astro").read_text(encoding="utf-8")
CHANNELS = (SITE_ROOT / "src/config/channels.ts").read_text(encoding="utf-8")
SCHEMA = (SITE_ROOT / "src/content.config.ts").read_text(encoding="utf-8")


class CrimeFeedPageTests(unittest.TestCase):
    def test_crime_index_uses_telegram_feed_instead_of_event_cards(self):
        self.assertIn('getCollection("crimeFeed")', PAGE)
        self.assertIn("TelegramPostCard", PAGE)
        self.assertNotIn("EventCard", PAGE)
        self.assertNotIn("event.title", PAGE)

    def test_each_post_receives_confirmed_max_channel(self):
        self.assertIn("maxUrl={CRIME_CHANNELS.max.url}", PAGE)
        self.assertIn("https://max.ru/channel_truecrime_news", CHANNELS)

    def test_crime_feed_has_a_valid_content_collection(self):
        self.assertIn('base: "./src/content/crime-feed"', SCHEMA)
        self.assertIn("crimeFeed", SCHEMA)


if __name__ == "__main__":
    unittest.main()
