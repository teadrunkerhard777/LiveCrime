import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SITE_ROOT = PROJECT_ROOT / "site"
PAGE = (SITE_ROOT / "src/pages/mma/index.astro").read_text(encoding="utf-8")
CHANNELS = (SITE_ROOT / "src/config/channels.ts").read_text(encoding="utf-8")
SCHEMA = (SITE_ROOT / "src/content.config.ts").read_text(encoding="utf-8")
WORKFLOW = (PROJECT_ROOT / ".github/workflows/mma-feed.yml").read_text(encoding="utf-8")


class MmaPageTests(unittest.TestCase):
    def test_page_uses_mma_feed_and_confirmed_channels(self):
        self.assertIn('getCollection("mma")', PAGE)
        self.assertIn("TelegramPostCard", PAGE)
        self.assertIn("https://t.me/MMA_TODAY777", CHANNELS)
        self.assertIn("https://max.ru/channel_MMA_TODAY", CHANNELS)
        self.assertIn("maxUrl={MMA_CHANNEL.max.url}", PAGE)

    def test_feed_has_content_schema(self):
        self.assertIn('base: "./src/content/mma"', SCHEMA)
        self.assertIn("mma", SCHEMA)

    def test_feed_runs_once_in_the_evening_without_secrets(self):
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn('cron: "20 15 * * *"', WORKFLOW)
        self.assertIn("--channel MMA_TODAY777", WORKFLOW)
        self.assertIn("git add site/src/content/mma", WORKFLOW)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", WORKFLOW)
        self.assertNotIn("TELEGRAM_CHAT_ID", WORKFLOW)
        self.assertIn("actions/deploy-pages@v5", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
