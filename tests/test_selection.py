import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock

from config import (
    CONTEXTUAL_TOPICS,
    CRIME_CONTEXT_KEYWORDS,
    EXCLUDE_KEYWORDS,
    MIN_PUBLICATION_SCORE,
    SCORE_RULES,
    STRONG_TOPICS,
    TOPICS,
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


def strict_filter(news_items):
    return filter_by_topics(
        news_items,
        TOPICS,
        EXCLUDE_KEYWORDS,
        CRIME_CONTEXT_KEYWORDS,
        STRONG_TOPICS,
        CONTEXTUAL_TOPICS,
    )


class StrictTrueCrimeTests(unittest.TestCase):
    def test_real_false_positives_are_rejected(self):
        titles = [
            "Лондонцы столкнулись с неочевидным последствием аномальной жары",
            "Украину обвинили в экспериментах в духовной сфере",
            "Врач предупредил о последствиях скопления грязи в пупке",
            "Россиянка спустя 20 лет разыскала подругу детства благодаря соцсетям",
        ]

        self.assertEqual(strict_filter([make_news_item(t) for t in titles]), [])

    def test_real_crime_cases_are_accepted(self):
        titles = [
            "Мужчину задержали по подозрению в убийстве",
            "Полиция разыскивает подозреваемого в убийстве",
            "Россиянина обвинили в мошенничестве",
            "Суд вынес приговор обвиняемому в убийстве",
            "Врача задержали по подозрению в убийстве пациента",
            "Медсестру обвинили в мошенничестве",
            "Следствие возбудило уголовное дело после нападения",
        ]

        result = strict_filter([make_news_item(t) for t in titles])

        self.assertEqual(len(result), len(titles))
        self.assertTrue(all(item["strong_topics"] for item in result))

    def test_weak_topic_needs_supporting_crime_context(self):
        [item] = strict_filter([
            make_news_item("Мужчине предъявили обвинение")
        ])

        self.assertEqual(item["strong_topics"], [])
        self.assertEqual(item["contextual_topics"], ["обвин"])
        self.assertIn("explicit context", item["admission_reason"])

    def test_word_start_matching_rejects_consequences(self):
        item = make_news_item("Неочевидные последствия жары")

        strict_filter([item])

        self.assertNotIn("следств", item["matched_topics"])

    def test_suicide_topics_do_not_turn_into_murder(self):
        items = strict_filter([
            make_news_item("Мужчина совершил самоубийство"),
            make_news_item("Следователи подтвердили суицид"),
        ])

        self.assertEqual(items[0]["matched_topics"], ["самоубий"])
        self.assertEqual(items[1]["matched_topics"], ["суицид"])
        self.assertNotIn("#убийство", generate_tags(items[0], {
            "самоубий": "#суицид",
            "убий": "#убийство",
        }))


class SeverityRankingTests(unittest.TestCase):
    def test_minimum_score_removes_weak_procedural_news(self):
        news = strict_filter([
            make_news_item("Мужчине предъявили обвинение"),
            make_news_item("Раскрыто мошенничество"),
        ])
        add_scores(news, SCORE_RULES)

        result = filter_by_minimum_score(news, MIN_PUBLICATION_SCORE)

        self.assertEqual([item["title"] for item in result], [
            "Раскрыто мошенничество"
        ])

    def test_murder_has_highest_severity_score(self):
        news = [
            make_news_item("Судебное заседание по уголовному делу"),
            make_news_item("Раскрыто мошенничество"),
            make_news_item("Раскрыто убийство"),
            make_news_item("Проведено задержание подозреваемого"),
        ]

        ranked = sort_by_score(news, SCORE_RULES)

        self.assertEqual(ranked[0]["title"], "Раскрыто убийство")
        self.assertEqual(ranked[0]["score"], 10)

    def test_equal_scores_keep_input_order(self):
        first = make_news_item("Первое мошенничество")
        second = make_news_item("Второе мошенничество")

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
