import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "site-intake.yml"


class SiteIntakeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_workflow_supports_daily_and_manual_runs(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn('cron: "17 7 * * *"', self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_workflow_prepares_only_one_private_candidate(self):
        self.assertIn("generator.import_published", self.workflow)
        self.assertIn("--limit 1", self.workflow)
        self.assertIn("--scan-limit 25", self.workflow)
        self.assertIn("--multiple-homicide-only", self.workflow)
        self.assertIn("actions/upload-artifact@v6", self.workflow)
        self.assertIn("site/data/inbox/*.json", self.workflow)
        self.assertLess(
            self.workflow.index("Upload private review candidate"),
            self.workflow.index("Save site intake boundary"),
        )

    def test_workflow_commits_only_site_state(self):
        self.assertIn("contents: write", self.workflow)
        self.assertIn("git add site/data/generator-state.json", self.workflow)
        self.assertNotIn("git add storage/published.json", self.workflow)
        self.assertNotIn("python main.py", self.workflow)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", self.workflow)
        self.assertNotIn("TELEGRAM_CHAT_ID", self.workflow)


if __name__ == "__main__":
    unittest.main()
