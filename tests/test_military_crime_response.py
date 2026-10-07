import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import main
from config import MAX_EVENT_AGE_DAYS, SCORE_RULES
from processing.filters import calculate_score, filter_by_event_policy
from tests.test_selection import hard_filter, make_news_item


REAL_TITLE = "Американских военных заставят думать 30 дней после убийства женщины морпехом в Японии"
REAL_LEAD = (
    "Американские военные в японской префектуре Окинава объявили оперативную "
    "паузу на 48 часов и запретили выход за пределы базы после того, как "
    "морской пехотинец был арестован по подозрению в убийстве 39-летней "
    "гражданки Японии. Об этом сообщает Fox News."
)


class MilitaryCrimeResponseTests(unittest.TestCase):
    def test_real_response_keeps_diagnostics_but_is_rejected(self):
        item = make_news_item(REAL_TITLE, REAL_LEAD)
        self.assertEqual(hard_filter([item]), [])
        self.assertEqual(item["matched_topics"], ["убий", "арест"])
        self.assertEqual(calculate_score(item, SCORE_RULES), 11)
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "military_crime_response")

    def test_response_detected_after_article_loading(self):
        item = make_news_item(REAL_TITLE)
        self.assertEqual(hard_filter([item]), [item])
        item["article_text"] = REAL_LEAD
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_restriction_headlines_are_not_tied_to_japan(self):
        for title in (
            "Военным запретили выход с базы после убийства женщины",
            "Командование объявило оперативную паузу из-за убийства туристки",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_direct_crime_and_arrest_reports_are_preserved(self):
        for title in (
            "Морпех убил женщину в гостинице",
            "Военнослужащий застрелил сослуживца на базе",
            "Американского морпеха арестовали за убийство женщины",
            "Полиция задержала мужчину по делу об убийстве возле парка",
            "Солдат убил коллегу; военным запретили выход после убийства женщины",
            "Военным запретили выход после убийства женщины, но солдат убил коллегу",
        ):
            with self.subTest(title=title):
                item = make_news_item(title, REAL_LEAD)
                self.assertEqual(hard_filter([item]), [item])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_late_restriction_paragraph_does_not_block_case(self):
        item = make_news_item(REAL_TITLE, "Следователи установили обстоятельства убийства.")
        item["article_text"] = item["description"] + "\n\n" + REAL_LEAD
        self.assertEqual(hard_filter([item]), [item])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_no_causal_crime_link_or_military_context_is_not_blocked(self):
        for title in (
            "Военным запретили выход с базы; следователи раскрыли убийство",
            "Родственникам запретили выход из дома после убийства женщины",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [item])

    def test_safe_pipeline_does_not_select_response_or_write_history(self):
        item = make_news_item(REAL_TITLE, REAL_LEAD)
        item["published_at"] = datetime.now(timezone.utc)
        output = StringIO()
        with (
            patch.object(main, "DRY_RUN", True),
            patch.object(main, "collect_enabled_news", return_value=[item]),
            patch.object(main, "load_selected_article_text"),
            patch.object(main, "load_history", return_value=[]),
            patch.object(main, "save_history") as save,
            patch.object(main, "publish_selected_news", return_value=False) as publish,
            redirect_stdout(output),
        ):
            main.run()
        self.assertEqual(publish.call_args.args[0], [])
        save.assert_not_called()
        self.assertIn("Выбрано для публикации: 0", output.getvalue())
