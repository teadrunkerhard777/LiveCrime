import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock

from config import (
    CONDITIONAL_SERIOUS_TOPICS,
    CONTEXTUAL_TOPICS,
    EXCLUDE_KEYWORDS,
    MIN_PUBLICATION_SCORE,
    SCORE_RULES,
    SERIOUS_OUTCOME_KEYWORDS,
    STRONG_TOPICS,
    TOPICS,
    TOPIC_TAGS,
)
from generation.post_generator import generate_tags
from main import publish_selected_news
from processing.filters import (
    add_scores,
    filter_by_minimum_score,
    filter_by_topics,
    sort_by_score,
)


def make_news_item(title, description=""):
    return {
        "title": title,
        "description": description,
        "url": "https://example.com/news",
        "source": "Тест",
        "published_at": None,
    }


def hard_filter(news_items):
    return filter_by_topics(
        news_items,
        TOPICS,
        EXCLUDE_KEYWORDS,
        SERIOUS_OUTCOME_KEYWORDS,
        STRONG_TOPICS,
        CONTEXTUAL_TOPICS,
        CONDITIONAL_SERIOUS_TOPICS,
    )


class HardTrueCrimeTests(unittest.TestCase):
    def test_required_weak_crime_cases_are_rejected(self):
        titles = [
            "Москвич задержан после ограбления магазина",
            "Курьер мошенников задержан",
            "Россиянина обвинили в мошенничестве",
            "Подозреваемого в краже ноутбука задержали",
            "Мужчину задержали с наркотиками",
            "Мужчина избил прохожего",
            "Подростки избили сверстника",
            "Мужчину обвинили в покушении",
            "Полиция сообщила о похищении человека",
        ]

        self.assertEqual(hard_filter([make_news_item(t) for t in titles]), [])

    def test_required_hard_true_crime_cases_are_accepted(self):
        titles = [
            "Мужчину задержали по подозрению в убийстве",
            "Суд вынес приговор за изнасилование",
            "Подозреваемого арестовали после расстрела двух человек",
            "Следователи раскрыли серию убийств",
            "Женщина совершила самоубийство",
            "Мужчина избил прохожего до смерти",
            "Вооружённое нападение закончилось гибелью двух человек",
        ]

        result = hard_filter([make_news_item(t) for t in titles])

        self.assertEqual(len(result), len(titles))
        self.assertTrue(all(item["strong_topics"] for item in result))

    def test_old_real_false_positives_stay_rejected(self):
        titles = [
            "Лондонцы столкнулись с неочевидным последствием аномальной жары",
            "Украину обвинили в экспериментах в духовной сфере",
            "Врач предупредил о последствиях скопления грязи в пупке",
            "Россиянка спустя 20 лет разыскала подругу детства благодаря соцсетям",
        ]

        self.assertEqual(hard_filter([make_news_item(t) for t in titles]), [])

    def test_contextual_topics_cannot_open_filter_by_accumulating(self):
        item = make_news_item(
            "Полиция задержала обвиняемого в краже и мошенничестве"
        )

        self.assertEqual(hard_filter([item]), [])
        self.assertEqual(item["strong_topics"], [])

    def test_attempt_language_does_not_match_killed_form(self):
        item = make_news_item(
            "Премьера обвинили в покушении",
            "Следствие заявило, что подозреваемый пытался убить политика.",
        )

        self.assertEqual(hard_filter([item]), [])
        self.assertNotIn("убит", item["matched_topics"])

    def test_fatal_assault_records_derived_serious_topic(self):
        [item] = hard_filter([
            make_news_item("Мужчина избил прохожего до смерти")
        ])

        self.assertIn("избил + до смерти", item["strong_topics"])
        self.assertIn("severe outcome", item["admission_reason"])

    def test_word_start_matching_rejects_consequences(self):
        item = make_news_item("Неочевидные последствия жары")

        hard_filter([item])

        self.assertNotIn("следств", item["matched_topics"])

    def test_all_suicide_forms_are_serious_without_murder_tag(self):
        titles = [
            "Мужчина совершил самоубийство",
            "Следователи подтвердили суицид",
            "Мужчина покончил с собой",
            "Женщина покончила с собой",
        ]

        items = hard_filter([make_news_item(t) for t in titles])

        self.assertEqual(len(items), 4)
        for item in items:
            tags = generate_tags(item, TOPIC_TAGS)
            self.assertIn("#суицид", tags)
            self.assertNotIn("#убийство", tags)


class SeverityRankingTests(unittest.TestCase):
    def test_minimum_score_keeps_hard_topic(self):
        news = hard_filter([
            make_news_item("Раскрыто убийство"),
            make_news_item("Мужчина совершил самоубийство"),
        ])
        add_scores(news, SCORE_RULES)

        result = filter_by_minimum_score(news, MIN_PUBLICATION_SCORE)

        self.assertEqual(len(result), 2)
        self.assertTrue(
            all(item["score"] >= MIN_PUBLICATION_SCORE for item in result)
        )

    def test_murder_ranks_above_rape_and_suicide(self):
        news = hard_filter([
            make_news_item("Подтверждено самоубийство"),
            make_news_item("Раскрыто изнасилование"),
            make_news_item("Раскрыто убийство"),
        ])

        ranked = sort_by_score(news, SCORE_RULES)

        self.assertEqual(ranked[0]["title"], "Раскрыто убийство")
        self.assertEqual(ranked[0]["score"], 10)

    def test_contextual_score_bonus_is_capped(self):
        [item] = hard_filter([
            make_news_item(
                "Полиция задержала обвиняемого за убийство",
                "Арест, уголовное дело, следствие, розыск и приговор.",
            )
        ])

        add_scores([item], SCORE_RULES)

        self.assertEqual(item["score"], 13)

    def test_equal_scores_keep_input_order(self):
        first = make_news_item("Первое убийство")
        second = make_news_item("Второе убийство")

        ranked = sort_by_score([first, second], SCORE_RULES)

        self.assertEqual(ranked, [first, second])

    def test_zero_selection_makes_no_telegram_calls(self):
        send_post = Mock()
        send_photo = Mock()
        add_history = Mock()

        with redirect_stdout(StringIO()):
            changed = publish_selected_news(
                [],
                [],
                dry_run=False,
                post_mode="single",
                send_post=send_post,
                send_photo=send_photo,
                add_history=add_history,
            )

        self.assertFalse(changed)
        send_post.assert_not_called()
        send_photo.assert_not_called()
        add_history.assert_not_called()


if __name__ == "__main__":
    unittest.main()
