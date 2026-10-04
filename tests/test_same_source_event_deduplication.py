import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path

from processing.deduplicator import (
    build_event_fingerprint,
    compare_event_fingerprints,
    remove_duplicates,
)
from storage.history import add_to_history, is_published
from test_event_deduplication import make_real_duplicate_pair


class SameSourceEventDeduplicationTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).parent / "fixtures" / "japan_marine_duplicates.json"
        items = json.loads(fixture.read_text(encoding="utf-8"))
        self.history_item = items["first"]
        self.candidate = items["second"]
        # Текущая статья получает fingerprint из текста, старая история — нет.
        self.candidate.pop("event_fingerprint")
        self.candidate["strong_topics"] = ["убий"]
        self.candidate["published_at"] = datetime.fromisoformat(
            self.candidate["published_at"]
        )

    def test_real_same_source_repeat_is_blocked_by_legacy_fingerprint(self):
        result = compare_event_fingerprints(self.history_item, self.candidate)
        self.assertLess(result["title_similarity"], 0.75)
        self.assertLess(result["token_overlap"], 0.45)
        self.assertTrue(result["lead_match"])
        self.assertGreaterEqual(result["lead_overlap"], 0.45)
        self.assertTrue(is_published(self.candidate, [self.history_item]))

    def test_repeat_is_merged_inside_one_run_and_reason_is_logged(self):
        output = StringIO()
        with redirect_stdout(output):
            selected = remove_duplicates(
                [self.history_item, self.candidate], debug=True
            )
        self.assertEqual(len(selected), 1)
        self.assertIn("lead overlap:", output.getvalue())

    def test_existing_dense_comparison_also_works_with_same_source(self):
        first, second = make_real_duplicate_pair()
        second["source"] = first["source"]
        self.assertTrue(compare_event_fingerprints(first, second)["is_duplicate"])

    def test_same_country_but_other_island_is_not_enough(self):
        self.candidate["article_text"] = self.candidate["article_text"].replace(
            "Наха", "Саппоро"
        ).replace("Окинава", "Хоккайдо").replace("Окинавы", "Хоккайдо")
        self.assertFalse(is_published(self.candidate, [self.history_item]))

    def test_no_explicit_local_place_does_not_open_lead_comparison(self):
        self.candidate["article_text"] = self.candidate["article_text"].replace(
            "в городе Наха на острове Окинава", "в Японии"
        )
        result = compare_event_fingerprints(self.history_item, self.candidate)
        self.assertFalse(result["lead_match"])
        self.assertFalse(result["is_duplicate"])

    def test_different_facts_in_same_local_place_are_not_merged(self):
        self.candidate["title"] = "В Японии раскрыли убийство пенсионера"
        self.candidate["article_text"] = (
            "В городе Наха на острове Окинава сосед зарезал пенсионера "
            "в квартире из-за наследства. Родственники обнаружили нож. "
            "Подозреваемый признался после экспертизы."
        )
        self.assertFalse(is_published(self.candidate, [self.history_item]))

    def test_missing_date_and_old_date_remain_ineligible_for_event_merge(self):
        for value in (None, datetime.fromisoformat("2026-10-07T09:36:26+03:00")):
            with self.subTest(value=value):
                self.candidate["published_at"] = value
                self.assertFalse(is_published(self.candidate, [self.history_item]))

    def test_different_event_family_is_not_merged(self):
        self.candidate["strong_topics"] = ["изнасил"]
        self.assertFalse(is_published(self.candidate, [self.history_item]))

    def test_history_without_fingerprint_remains_url_only(self):
        self.history_item.pop("event_fingerprint")
        self.assertFalse(is_published(self.candidate, [self.history_item]))

    def test_new_fingerprint_is_compact_and_history_updated_in_memory_only(self):
        fingerprint = build_event_fingerprint(self.candidate)
        self.assertIn("окинав", fingerprint["local_locations"])
        self.assertTrue(fingerprint["lead_tokens"])
        history = []
        add_to_history(self.candidate, history)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["event_fingerprint"], fingerprint)
        self.assertNotIn("article_text", history[0])
