import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SITE_ROOT.parent
PAGE = (SITE_ROOT / "src/pages/gadgets/index.astro").read_text(encoding="utf-8")
SCHEMA = (SITE_ROOT / "src/content.config.ts").read_text(encoding="utf-8")
CHANNELS = (SITE_ROOT / "src/config/channels.ts").read_text(encoding="utf-8")
WORKFLOW = (PROJECT_ROOT / ".github/workflows/gadgets-feed.yml").read_text(encoding="utf-8")


class GadgetsPageTests(unittest.TestCase):
    def test_page_uses_gadgets_feed_and_confirmed_channels(self):
        self.assertIn('getCollection("gadgets")', PAGE)
        self.assertIn("GADGETS_CHANNEL.telegram.url", PAGE)
        self.assertIn("GADGETS_CHANNEL.max.url", PAGE)
        self.assertIn("https://t.me/trends_brands_money", CHANNELS)
        self.assertIn("https://max.ru/channel_trends_and_brands", CHANNELS)

    def test_feed_has_content_schema(self):
        self.assertIn('base: "./src/content/gadgets"', SCHEMA)
        self.assertIn("gadgets", SCHEMA)

    def test_feed_runs_once_in_the_evening_without_secrets(self):
        self.assertIn('cron: "0 16 * * *"', WORKFLOW)
        self.assertIn("--channel trends_brands_money", WORKFLOW)
        self.assertIn("git add site/src/content/gadgets", WORKFLOW)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
