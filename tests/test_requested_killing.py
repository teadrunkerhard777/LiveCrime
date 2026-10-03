import unittest

from config import MAX_EVENT_AGE_DAYS, SCORE_RULES
from processing.filters import calculate_score, filter_by_event_policy
from tests.test_selection import hard_filter, make_news_item


class RequestedKillingTests(unittest.TestCase):
    def test_real_flydubai_headline_is_rejected(self):
        item = make_news_item(
            "«Он несколько раз просил, чтобы его убили». Пассажир рейса "
            "FlyDubai рассказал, как помог обезвредить второго пилота",
            "Врач Шота Мусаев рассказал о ситуации на борту самолёта.",
        )

        self.assertEqual(hard_filter([item]), [])
        self.assertNotIn("убил", item["matched_topics"])
        self.assertEqual(calculate_score(item, SCORE_RULES), 0)
        self.assertEqual(
            item["rejection_reason"],
            "requested killing is not a completed homicide",
        )
        self.assertEqual(
            item["ignored_homicide_fragments"],
            ["просил, чтобы его убили"],
        )

    def test_request_variants_do_not_admit_story(self):
        for title in (
            "Мужчина попросил, чтобы его убили",
            "Женщина просила, чтобы её убили",
            "Пилот умолял, чтобы его убили",
            "Он попросил … чтобы мы его убили",
            "Мужчина просил, чтобы он был убит",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [])
                self.assertEqual(calculate_score(item, SCORE_RULES), 0)

    def test_separate_completed_murder_is_preserved(self):
        for title, description in (
            ("Мужчина убил знакомого", "Затем просил, чтобы его убили."),
            ("Мужчина просил, чтобы его убили", "Ранее он убил знакомого."),
            ("Мужчина просил, чтобы его убили", "Женщина найдена убитой."),
            ("Мужчина просил, чтобы его убили", "Расследуется убийство соседа."),
        ):
            with self.subTest(title=title, description=description):
                item = make_news_item(title, description)
                self.assertEqual(hard_filter([item]), [item])
                self.assertGreaterEqual(calculate_score(item, SCORE_RULES), 10)

    def test_request_does_not_cancel_standalone_attempt_rejection(self):
        item = make_news_item(
            "Мужчину обвиняют в покушении на убийство",
            "Задержанный просил, чтобы его убили. Потерпевший выжил.",
        )
        item["article_text"] = "Он несколько раз попросил … чтобы его убили."

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [],
        )
        self.assertEqual(item["event_policy_rejection"], "standalone_attempt")

    def test_real_killing_in_sentence_after_request_is_preserved(self):
        item = make_news_item(
            "Он просил, чтобы ему помогли. Затем он убил соседа."
        )
        self.assertEqual(hard_filter([item]), [item])


if __name__ == "__main__":
    unittest.main()
