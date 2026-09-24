import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "site-intake.yml"
CRIME_FEED_PATH = PROJECT_ROOT / ".github" / "workflows" / "crime-feed.yml"


class SiteIntakeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.crime_feed = CRIME_FEED_PATH.read_text(encoding="utf-8")

    def test_legacy_card_workflow_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_crime_feed_runs_three_times_and_can_run_manually(self):
        self.assertIn("workflow_dispatch:", self.crime_feed)
        self.assertIn('cron: "0 3,9,15 * * *"', self.crime_feed)
        self.assertIn("cancel-in-progress: false", self.crime_feed)

    def test_crime_feed_imports_public_channel_without_secrets(self):
        self.assertIn("--channel truecrime_news", self.crime_feed)
        self.assertIn("--content src/content/crime-feed", self.crime_feed)
        self.assertIn("git add site/src/content/crime-feed", self.crime_feed)
        self.assertNotIn("storage/published.json", self.crime_feed)
        self.assertNotIn("python main.py", self.crime_feed)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", self.crime_feed)
        self.assertNotIn("TELEGRAM_CHAT_ID", self.crime_feed)
        self.assertNotIn("--force", self.crime_feed)

    def test_crime_feed_builds_and_deploys_the_latest_site(self):
        self.assertIn("pages: write", self.crime_feed)
        self.assertIn("id-token: write", self.crime_feed)
        self.assertIn("needs: import-posts", self.crime_feed)
        self.assertIn("withastro/action@v6", self.crime_feed)
        self.assertIn("actions/deploy-pages@v5", self.crime_feed)
        self.assertIn("ref: ${{ github.ref_name }}", self.crime_feed)


if __name__ == "__main__":
    unittest.main()
