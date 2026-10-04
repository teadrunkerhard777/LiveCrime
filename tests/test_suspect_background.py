import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import main

from config import MAX_EVENT_AGE_DAYS, SCORE_RULES
from processing.filters import calculate_score, filter_by_event_policy
from tests.test_selection import hard_filter, make_news_item


REAL_TITLE = "Подозреваемого в убийстве ранили после аварии и перестрелки с полицейскими"
REAL_TEXT = (
    "В американском городе Эшберн сотрудники полиции ранили мужчину, "
    "которого разыскивали в связи с расследованием убийства. "
    "Перед стрельбой произошли автомобильная погоня и авария.\n\n"
    "Розыск подозреваемого был связан с убийством, совершенным 2 октября "
    "в округе Генри. Уже на следующий день правоохранительные органы "
    "округа Тернер получили ориентировку с описанием разыскиваемого мужчины."
)


class SuspectBackgroundTests(unittest.TestCase):
    def test_real_post_is_rejected_after_article_loading_despite_high_score(self):
        item = make_news_item(REAL_TITLE)
        self.assertEqual(hard_filter([item]), [item])
        self.assertEqual(item["matched_topics"], ["убий", "подозрев"])
        self.assertEqual(calculate_score(item, SCORE_RULES), 11)
        item["article_text"] = REAL_TEXT
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "nonfatal_suspect_incident")

    def test_description_fallback_and_missing_body_are_safe(self):
        for description in (REAL_TEXT, ""):
            with self.subTest(description=description):
                item = make_news_item(REAL_TITLE, description)
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_nonfatal_pursuit_with_homicide_background_is_rejected(self):
        for title in (
            "Подозреваемый в убийстве ранен в перестрелке",
            "Обвиняемый в убийстве попал в аварию во время погони",
            "Разыскиваемого за убийство ранили полицейские",
        ):
            with self.subTest(title=title):
                item = make_news_item(title, REAL_TEXT)
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_fatal_current_incident_in_body_is_preserved(self):
        for body in (
            "При перестрелке погиб полицейский.",
            "Полицейские застрелили подозреваемого при задержании.",
            "Во время погони мужчина убил прохожего.",
            "Накануне во время перестрелки погиб полицейский.",
            "Раненый мужчина скончался в больнице.",
        ):
            with self.subTest(body=body):
                item = make_news_item(REAL_TITLE)
                item["article_text"] = REAL_TEXT + "\n\n" + body
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_safe_main_run_does_not_select_or_publish_real_case(self):
        item = make_news_item(REAL_TITLE)
        item["published_at"] = datetime.now(timezone.utc)
        item["article_text"] = REAL_TEXT
        output = StringIO()
        # Проверяем реальный порядок pipeline без HTTP и записи истории.
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
        self.assertTrue(publish.call_args.args[2])
        save.assert_not_called()
        self.assertIn("Выбрано для публикации: 0", output.getvalue())
        self.assertIn("hard crime is search background", output.getvalue())

    def test_previous_fatal_incident_does_not_open_filter(self):
        item = make_news_item(REAL_TITLE)
        item["article_text"] = REAL_TEXT + "\nРанее он убил полицейского."
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_completed_killing_in_headline_is_preserved(self):
        item = make_news_item(
            "Подозреваемый в убийстве застрелил полицейского в перестрелке"
        )
        self.assertEqual(hard_filter([item]), [item])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_murder_reporting_and_investigation_are_unchanged(self):
        for title in (
            "В городе убили женщину",
            "Подозреваемого в убийстве женщины задержали по горячим следам",
            "Следствие раскрыло убийство мужчины",
            "Мужчина обвиняется в убийстве знакомого в ходе пьяной ссоры",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [item])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])
