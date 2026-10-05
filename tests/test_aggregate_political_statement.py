import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import main
from config import MAX_EVENT_AGE_DAYS, SCORE_RULES
from processing.filters import calculate_score, filter_by_event_policy
from tests.test_selection import hard_filter, make_news_item


REAL_TITLE = "Почти все прибывающие в европейскую страну беженки подвергались изнасилованиям"
REAL_TEXT = (
    "Шабана Махмуд заявила, что почти все женщины, которые пытаются добраться "
    "до Британии на небольших лодках из северной Франции, были изнасилованы "
    "во время путешествия, пишет The Guardian.\n\n"
    "В интервью подкасту министр внутренних дел заявил, что ультраправые "
    "активисты в балаклавах убьют или вышвырнут меня из моей собственной "
    "страны, если они придут к власти."
)


class AggregatePoliticalStatementTests(unittest.TestCase):
    def test_real_post_is_rejected_with_original_topic_diagnostics(self):
        item = make_news_item(REAL_TITLE, REAL_TEXT)
        self.assertEqual(hard_filter([item]), [])
        self.assertEqual(item["matched_topics"], ["изнасил"])
        self.assertEqual(calculate_score(item, SCORE_RULES), 9)
        self.assertFalse(item["strict_filter_passed"])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "aggregate_political_statement")

    def test_missing_rss_description_is_checked_after_article_loading(self):
        item = make_news_item(REAL_TITLE)
        self.assertEqual(hard_filter([item]), [item])
        item["article_text"] = REAL_TEXT
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_other_names_groups_and_quantifiers_are_supported(self):
        for title in (
            "Большинство приезжающих женщин подвергались изнасилованию",
            "Практически все женщины на маршруте были изнасилованы",
            "90 процентов женщин были изнасилованы по пути в страну",
            "90% прибывающих женщин подверглись изнасилованию",
        ):
            with self.subTest(title=title):
                item = make_news_item(title, "Другой министр рассказал об этом в интервью.")
                self.assertEqual(hard_filter([item]), [])

    def test_real_cases_against_refugees_and_groups_are_preserved(self):
        for title in (
            "Мужчина изнасиловал беженку возле лагеря",
            "Полицейские задержали подозреваемого в изнасиловании беженки",
            "Министр сообщил об изнасиловании женщины в лагере",
            "В городе убили женщину-беженку",
            "Трое мужчин изнасиловали двух женщин",
            "Почти все заложницы были изнасилованы: по делу задержали охранника",
        ):
            with self.subTest(title=title):
                item = make_news_item(title, "Министр заявил о расследовании конкретного дела.")
                self.assertEqual(hard_filter([item]), [item])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_random_late_political_quote_does_not_trigger_rejection(self):
        item = make_news_item(REAL_TITLE)
        item["article_text"] = "Описание обстоятельств. " * 80 + REAL_TEXT
        self.assertEqual(hard_filter([item]), [item])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_generalization_without_political_statement_is_not_globally_blocked(self):
        item = make_news_item(REAL_TITLE, "Следствие расследует серию нападений.")
        self.assertEqual(hard_filter([item]), [item])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_safe_main_run_does_not_select_or_publish_statement(self):
        item = make_news_item(REAL_TITLE, REAL_TEXT)
        item["published_at"] = datetime.now(timezone.utc)
        with (
            patch.object(main, "DRY_RUN", True),
            patch.object(main, "collect_enabled_news", return_value=[item]),
            patch.object(main, "load_selected_article_text") as load,
            patch.object(main, "load_history", return_value=[]),
            patch.object(main, "save_history") as save,
            patch.object(main, "publish_selected_news", return_value=False) as publish,
            redirect_stdout(StringIO()),
        ):
            main.run()
        self.assertEqual(load.call_args.args[0], [])
        self.assertEqual(publish.call_args.args[0], [])
        save.assert_not_called()
