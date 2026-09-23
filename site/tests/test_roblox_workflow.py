import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (PROJECT_ROOT / ".github/workflows/roblox-feed.yml").read_text(encoding="utf-8")


class RobloxFeedWorkflowTests(unittest.TestCase):
    def test_feed_runs_twice_hourly_and_can_run_manually(self):
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn('cron: "7,37 * * * *"', WORKFLOW)
        self.assertIn("cancel-in-progress: false", WORKFLOW)

    def test_feed_imports_public_channel_without_telegram_secrets(self):
        self.assertIn("generator.import_roblox_telegram", WORKFLOW)
        self.assertIn("git add site/src/content/roblox", WORKFLOW)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", WORKFLOW)
        self.assertNotIn("TELEGRAM_CHAT_ID", WORKFLOW)

    def test_feed_builds_and_deploys_site(self):
        self.assertIn("withastro/action@v6", WORKFLOW)
        self.assertIn("actions/deploy-pages@v5", WORKFLOW)
        self.assertIn("pages: write", WORKFLOW)
        self.assertIn("id-token: write", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
