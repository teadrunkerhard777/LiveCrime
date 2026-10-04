import unittest

from config import MAX_EVENT_AGE_DAYS, SCORE_RULES
from processing.filters import calculate_score, filter_by_event_policy
from tests.test_selection import hard_filter, make_news_item


class PoliticalDeathCommentaryTests(unittest.TestCase):
    def test_real_zakharova_proverb_is_rejected(self):
        item = make_news_item(
            "Захарова оценила визит Мерца в Киев фразой "
            "«убийцы возвращаются на место преступления»",
            "Официальный представитель МИД России Мария Захарова "
            "назвала пиаром на крови визит канцлера ФРГ Фридриха Мерца в Киев.",
        )
        self.assertEqual(hard_filter([item]), [])
        self.assertEqual(item["matched_topics"], ["убий", "преступ"])
        self.assertEqual(calculate_score(item, SCORE_RULES), 11)
        self.assertFalse(item["strict_filter_passed"])
        self.assertEqual(
            item["rejection_reason"],
            "political homicide rhetoric is not a concrete hard event",
        )
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "political_rhetoric")

    def test_proverb_variations_do_not_depend_on_name_or_quotes(self):
        for title in (
            "Министр оценил визит словами: убийцы всегда возвращаются на место преступления",
            'Дипломат прокомментировал визит: "убийца возвращается к месту преступления"',
            "Политик назвал поездку возвращением: убийцы возвращаются на место преступления",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

    def test_real_murder_with_same_quote_is_not_rejected_as_rhetoric(self):
        for title in (
            "Министр оценил убийство женщины фразой «убийцы возвращаются на место преступления»",
            "Полицейский назвал убийцу вернувшимся на место преступления",
            "Убийца вернулся на место преступления и убил свидетеля",
            "Захарова рассказала об убийстве женщины в Киеве",
        ):
            with self.subTest(title=title):
                item = make_news_item(title)
                self.assertEqual(hard_filter([item]), [item])
                self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_proverb_without_political_evaluation_does_not_block_true_crime(self):
        item = make_news_item(
            "Убийцы возвращаются на место преступления: полиция поймала преступника",
            "Мужчина убил соседку. Во время визита полицейские задержали убийцу.",
        )
        self.assertEqual(hard_filter([item]), [item])
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_article_only_political_context_is_checked_after_loading(self):
        item = make_news_item(
            "Представитель оценил поездку: убийцы возвращаются на место преступления"
        )
        self.assertEqual(hard_filter([item]), [item])
        item["article_text"] = "Дипломат МИД прокомментировал поездку канцлера."
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])

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
