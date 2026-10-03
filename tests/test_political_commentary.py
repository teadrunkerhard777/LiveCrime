import unittest

from config import MAX_EVENT_AGE_DAYS, SCORE_RULES
from processing.filters import calculate_score, filter_by_event_policy
from tests.test_selection import hard_filter, make_news_item


class PoliticalDeathCommentaryTests(unittest.TestCase):
    def test_real_medvedev_commentary_is_rejected(self):
        item = make_news_item(
            "Медведев раскрыл отношение Путина к убитому лидеру Ирана",
            "Президент России Владимир Путин высоко ценил верховного "
            "лидера Ирана Али Хаменеи. Медведев рассказал об этом в интервью.",
        )

        self.assertEqual(hard_filter([item]), [])
        # Сигнал действительно найден; причина отказа — формат материала.
        self.assertEqual(item["matched_topics"], ["убит"])
        self.assertEqual(calculate_score(item, SCORE_RULES), 10)
        self.assertFalse(item["strict_filter_passed"])
        self.assertEqual(
            item["rejection_reason"],
            "political commentary about a deceased leader",
        )
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "political_commentary")

    def test_condolences_and_memorial_commentary_are_rejected(self):
        for title in (
            "Путин выразил соболезнования семье убитого президента",
            "Политик почтил память погибшего лидера страны",
            "Министр осудил убийство президента",
        ):
            with self.subTest(title=title):
                self.assertEqual(hard_filter([make_news_item(title)]), [])

    def test_actual_crime_against_politician_is_preserved(self):
        for title in (
            "В стране убили президента",
            "Следователи раскрыли убийство лидера партии",
            "Убийцу депутата задержали в Москве",
            "В Иране мужчина убил соседку",
            "Путин рассказал об убийстве женщины в российском городе",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [item])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_commentary_without_political_victim_does_not_block_crime(self):
        item = make_news_item(
            "Следователь раскрыл отношение подозреваемого к убитому соседу"
        )
        self.assertEqual(hard_filter([item]), [item])


if __name__ == "__main__":
    unittest.main()
