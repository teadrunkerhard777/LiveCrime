import json
import tempfile
import unittest
from pathlib import Path

from generator.import_published import (
    GeneratorError,
    initialize_state,
    is_multiple_homicide_candidate,
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
            "tokens": ["пример", f"событие-{number}"],
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
        self.assertEqual(state["seen_event_keys"], [])
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
        self.assertEqual(len(state["seen_event_keys"]), 1)

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

    def test_same_event_fingerprint_creates_only_one_candidate(self):
        old_item = make_item(1)
        first_report = make_item(2)
        second_report = make_item(3)
        second_report["event_fingerprint"] = first_report["event_fingerprint"]
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(self.history_path, [old_item, first_report, second_report])

        paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
            limit=2,
        )

        self.assertEqual(len(paths), 1)
        self.assertEqual(len(list(self.inbox_path.glob("*.json"))), 1)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["history_cursor"], 3)
        self.assertEqual(len(state["seen_event_keys"]), 1)

    def test_different_event_fingerprints_create_separate_candidates(self):
        old_item = make_item(1)
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(self.history_path, [old_item, make_item(2), make_item(3)])

        paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
            limit=2,
        )

        self.assertEqual(len(paths), 2)
        self.assertEqual(len(list(self.inbox_path.glob("*.json"))), 2)

    def test_missing_fingerprint_does_not_merge_different_urls(self):
        old_item = make_item(1)
        first_report = make_item(2)
        second_report = make_item(3)
        first_report.pop("event_fingerprint")
        second_report.pop("event_fingerprint")
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(self.history_path, [old_item, first_report, second_report])

        paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
            limit=2,
        )

        self.assertEqual(len(paths), 2)

    def test_legacy_state_without_seen_event_keys_remains_valid(self):
        old_item = make_item(1)
        new_item = make_item(2)
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state.pop("seen_event_keys")
        write_json(self.state_path, state)
        write_json(self.history_path, [old_item, new_item])

        paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
        )

        self.assertEqual(len(paths), 1)
        updated_state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(updated_state["seen_event_keys"]), 1)

    def test_multiple_homicide_filter_skips_single_victim_and_finds_next_item(self):
        old_item = make_item(1)
        single_victim = make_item(2)
        single_victim["title"] = "20-летняя женщина обвиняется в убийстве знакомого"
        multiple_victims = make_item(3)
        multiple_victims["title"] = "Мужчину обвинили в убийстве трех человек"
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(
            self.history_path,
            [old_item, single_victim, multiple_victims],
        )

        paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
            limit=1,
            scan_limit=2,
            multiple_homicide_only=True,
        )

        self.assertEqual(len(paths), 1)
        candidate = json.loads(paths[0].read_text(encoding="utf-8"))
        self.assertEqual(candidate["url"], multiple_victims["url"])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["history_cursor"], 3)

    def test_multiple_homicide_filter_requires_homicide_topic(self):
        item = make_item(2)
        item["title"] = "При пожаре погибли три человека"
        item["event_fingerprint"]["topics"] = []

        self.assertFalse(is_multiple_homicide_candidate(item))

    def test_multiple_homicide_filter_rejects_age_as_victim_count(self):
        item = make_item(2)
        item["title"] = "20-летняя женщина обвиняется в убийстве ребенка"

        self.assertFalse(is_multiple_homicide_candidate(item))

    def test_multiple_homicide_filter_accepts_explicit_counts(self):
        titles = [
            "Убийцу трех девочек обвинили в нападениях",
            "При нападении погибли 16 человек",
            "Следователи раскрыли двойное убийство",
        ]

        for title in titles:
            with self.subTest(title=title):
                item = make_item(2)
                item["title"] = title
                self.assertTrue(is_multiple_homicide_candidate(item))

    def test_multiple_homicide_filter_advances_past_rejected_items(self):
        old_item = make_item(1)
        rejected_items = [make_item(2), make_item(3)]
        for item in rejected_items:
            item["title"] = "Один человек погиб в результате конфликта"
        write_json(self.history_path, [old_item])
        initialize_state(self.history_path, self.state_path)
        write_json(self.history_path, [old_item, *rejected_items])

        paths = scan_new_items(
            self.history_path,
            self.state_path,
            self.inbox_path,
            limit=1,
            scan_limit=2,
            multiple_homicide_only=True,
        )

        self.assertEqual(paths, [])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["history_cursor"], 3)
        self.assertFalse(self.inbox_path.exists())


if __name__ == "__main__":
    unittest.main()
