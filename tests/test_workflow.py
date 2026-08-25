import os
import subprocess
import sys
import unittest
from pathlib import Path

from config import MAX_NEWS_PER_RUN, SOURCES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "livecrime.yml"


class ConfigTests(unittest.TestCase):
    def _read_dry_run_in_clean_process(self, env_value=None):
        """Импортирует config отдельно, чтобы проверить значение окружения."""

        env = os.environ.copy()
        env.pop("LIVECRIME_DRY_RUN", None)

        if env_value is not None:
            env["LIVECRIME_DRY_RUN"] = env_value

        result = subprocess.run(
            [sys.executable, "-c", "import config; print(config.DRY_RUN)"],
            cwd=PROJECT_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip()

    def test_local_dry_run_is_enabled_by_default(self):
        self.assertEqual(self._read_dry_run_in_clean_process(), "True")

    def test_workflow_can_disable_dry_run_through_environment(self):
        self.assertEqual(
            self._read_dry_run_in_clean_process("false"),
            "False",
        )

    def test_publication_scope_remains_restricted(self):
        enabled_sources = [
            source for source in SOURCES
            if source.get("enabled", True)
        ]

        self.assertEqual(MAX_NEWS_PER_RUN, 1)
        self.assertEqual(
            [source["name"] for source in enabled_sources],
            [
                "Lenta.ru",
                "АГН Москва: происшествия",
                "PeterburgMedia: происшествия",
                "116.ru: происшествия",
                "E1.ru: происшествия",
                "VN.ru: происшествия",
                "vtomske.ru: происшествия",
            ],
        )


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_workflow_is_manual_and_has_no_schedule(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("schedule:", self.workflow)
        self.assertNotIn("cron:", self.workflow)

    def test_workflow_has_write_permission_and_concurrency(self):
        self.assertIn("contents: write", self.workflow)
        self.assertIn("group: livecrime-autoposter", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_workflow_passes_secrets_and_enables_real_mode(self):
        self.assertIn("secrets.TELEGRAM_BOT_TOKEN", self.workflow)
        self.assertIn("secrets.TELEGRAM_CHAT_ID", self.workflow)
        self.assertIn('LIVECRIME_DRY_RUN: "false"', self.workflow)

    def test_history_is_committed_only_after_main(self):
        main_position = self.workflow.index("run: python main.py")
        commit_position = self.workflow.index(
            'git commit -m "Update LiveCrime publication history"'
        )

        self.assertLess(main_position, commit_position)
        self.assertIn(
            "git diff --quiet -- storage/published.json",
            self.workflow,
        )
        self.assertIn("git add storage/published.json", self.workflow)
        self.assertNotIn("git add .", self.workflow)
        self.assertNotIn("|| true", self.workflow)


if __name__ == "__main__":
    unittest.main()
