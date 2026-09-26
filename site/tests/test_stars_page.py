import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = PROJECT_ROOT / "site"
PAGE = (SITE_ROOT / "src/pages/stars/index.astro").read_text(encoding="utf-8")
CHANNELS = (SITE_ROOT / "src/config/channels.ts").read_text(encoding="utf-8")
SCHEMA = (SITE_ROOT / "src/content.config.ts").read_text(encoding="utf-8")
WORKFLOW = (PROJECT_ROOT / ".github/workflows/stars-feed.yml").read_text(encoding="utf-8")


class StarsPageTests(unittest.TestCase):
    def test_page_uses_stars_feed_and_confirmed_channels(self):
        self.assertIn('getCollection("stars")', PAGE)
        self.assertIn("TelegramPostCard", PAGE)
        self.assertIn("https://t.me/zvezdi_budni", CHANNELS)
        self.assertIn("https://max.ru/channel_zvezdi_budni", CHANNELS)
        self.assertIn("maxUrl={STARS_CHANNEL.max.url}", PAGE)

    def test_feed_has_content_schema(self):
        self.assertIn('base: "./src/content/stars"', SCHEMA)
        self.assertIn("stars", SCHEMA)

    def test_feed_runs_once_in_the_evening_without_secrets(self):
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn('cron: "30 15 * * *"', WORKFLOW)
        self.assertIn("--channel zvezdi_budni", WORKFLOW)
        self.assertIn("git add site/src/content/stars", WORKFLOW)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", WORKFLOW)
        self.assertNotIn("TELEGRAM_CHAT_ID", WORKFLOW)
        self.assertIn("actions/deploy-pages@v5", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
