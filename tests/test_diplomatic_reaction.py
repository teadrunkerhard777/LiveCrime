import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import main
from config import MAX_EVENT_AGE_DAYS, SCORE_RULES
from processing.filters import calculate_score, filter_by_event_policy
from tests.test_selection import hard_filter, make_news_item


REAL_TITLE = "Япония выразила протест послу США из-за убийства местной жительницы морпехом"
REAL_BODY = (
    "Тосимицу Мотэги. Фото: Issei Kato / Reuters\n\n"
    "МИД Японии выразил протест послу США Джорджу Глассу из-за убийства "
    "местной жительницы морпехом.\n\n"
    "Полиция японской префектуры Окинава арестовала 20-летнего американского "
    "военнослужащего авиабазы Футэмма по подозрению в ограблении и убийстве "
    "39-летней гражданки Японии. Тело погибшей было обнаружено в номере отеля."
)


class DiplomaticReactionTests(unittest.TestCase):
    def test_real_okinawa_reaction_is_rejected_without_history(self):
        item = make_news_item(REAL_TITLE)
        item["article_text"] = REAL_BODY
        self.assertEqual(hard_filter([item]), [])
        self.assertEqual(item["matched_topics"], ["убий"])
        self.assertEqual(calculate_score(item, SCORE_RULES), 10)
        self.assertFalse(item["strict_filter_passed"])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "diplomatic_reaction")

    def test_reactions_are_not_tied_to_country_or_person_name(self):
        for title in (
            "МИД выразил протест в связи с убийством гражданки за границей",
            "Министр иностранных дел заявил протест послу после убийства туриста",
            "МИД вызвал посла из-за убийства местной жительницы",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_context_available_only_in_body_is_checked_after_loading(self):
        item = make_news_item("Япония выразила протест из-за убийства женщины")
        self.assertEqual(hard_filter([item]), [item])
        item["article_text"] = REAL_BODY
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_direct_murder_and_arrest_reports_are_preserved(self):
        for title in (
            "Американского военного заподозрили в убийстве жительницы Окинавы",
            "Американский морской пехотинец арестован в Японии за убийство женщины",
            "Мужчину застрелили возле городского парка после давнего конфликта",
            "Полиция задержала мужчину по делу об убийстве возле парка",
            "В Японии убили посла США",
            "МИД сообщил об убийстве дипломата",
            "Морпех убил женщину; Япония выразила протест послу из-за убийства",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [item])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_nondiplomatic_protest_does_not_block_real_crime_reporting(self):
        item = make_news_item("Родственники выразили протест после убийства женщины")
        self.assertEqual(hard_filter([item]), [item])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_safe_pipeline_never_selects_the_real_reaction(self):
        item = make_news_item(REAL_TITLE)
        item["published_at"] = datetime.now(timezone.utc)
        item["article_text"] = REAL_BODY
        output = StringIO()
        with (
            patch.object(main, "DRY_RUN", True),
            patch.object(main, "collect_enabled_news", return_value=[item]),
            patch.object(main, "load_selected_article_text") as load,
            patch.object(main, "load_history", return_value=[]),
            patch.object(main, "save_history") as save,
            patch.object(main, "publish_selected_news", return_value=False) as publish,
            redirect_stdout(output),
        ):
            main.run()
        self.assertEqual(load.call_args.args[0], [])
        self.assertEqual(publish.call_args.args[0], [])
        save.assert_not_called()
        self.assertIn("Выбрано для публикации: 0", output.getvalue())
