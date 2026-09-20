import json
import tempfile
import unittest
from pathlib import Path

from generator.import_published import (
    GeneratorError,
    initialize_state,
    scan_new_items,
)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_item(number: int) -> dict:
    return {
        "title": f"Подтверждённая публикация номер {number}",
        "url": f"https://news.example/events/{number}",
        "published_at": f"2026-09-{number:02d}T12:00:00+05:00",
        "source": "Тестовый источник",
        "event_fingerprint": {
            "topics": ["homicide"],
            "tokens": ["пример"],
            "locations": ["екатеринбург"],
        },
    }


class PublishedHistoryImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.history_path = self.root / "storage" / "published.json"
        self.state_path = self.root / "site" / "data" / "generator-state.json"
        self.inbox_path = self.root / "site" / "data" / "inbox"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_initialization_skips_old_archive_and_preserves_history(self):
        history = [make_item(1), make_item(2)]
        write_json(self.history_path, history)
        before = self.history_path.read_bytes()

        state = initialize_state(self.history_path, self.state_path)

        self.assertEqual(state["history_cursor"], 2)
        self.assertEqual(state["last_history_url"], history[-1]["url"])
        self.assertFalse(self.inbox_path.exists())
        self.assertEqual(self.history_path.read_bytes(), before)

    def test_scan_creates_only_one_non_publishable_candidate(self):
        old_item = make_item(1)
        new_item = make_item(2)
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(self.history_path, [old_item, new_item])
        before = self.history_path.read_bytes()

        paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
        )

        self.assertEqual(len(paths), 1)
        candidate = json.loads(paths[0].read_text(encoding="utf-8"))
        self.assertEqual(candidate["url"], new_item["url"])
        self.assertEqual(candidate["section"], "crime")
        self.assertEqual(candidate["status"], "needs_review")
        self.assertFalse(candidate["quality_gate"]["publishable"])
        self.assertEqual(self.history_path.read_bytes(), before)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["history_cursor"], 2)

    def test_existing_candidate_makes_retry_idempotent(self):
        old_item = make_item(1)
        new_item = make_item(2)
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(self.history_path, [old_item, new_item])
        first_paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
        )
        original_candidate = first_paths[0].read_bytes()

        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["history_cursor"] = 1
        state["last_history_url"] = old_item["url"]
        write_json(self.state_path, state)
        second_paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
        )

        self.assertEqual(second_paths, first_paths)
        self.assertEqual(first_paths[0].read_bytes(), original_candidate)

    def test_changed_history_boundary_stops_import(self):
        history = [make_item(1)]
        write_json(self.history_path, history)
        initialize_state(self.history_path, self.state_path)
        replacement = make_item(2)
        write_json(self.history_path, [replacement, make_item(3)])

        with self.assertRaises(GeneratorError):
            scan_new_items(
                self.history_path,
                self.state_path,
                self.inbox_path,
            )

        self.assertFalse(self.inbox_path.exists())

    def test_invalid_new_item_does_not_advance_state(self):
        old_item = make_item(1)
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(self.history_path, [old_item, {"title": "Без ссылки"}])
        before_state = self.state_path.read_bytes()

        with self.assertRaises(GeneratorError):
            scan_new_items(
                self.history_path,
                self.state_path,
                self.inbox_path,
            )

        self.assertEqual(self.state_path.read_bytes(), before_state)
        self.assertFalse(self.inbox_path.exists())


if __name__ == "__main__":
    unittest.main()
