import unittest
from datetime import datetime, timezone

from config import MAX_EVENT_AGE_DAYS
from processing.filters import filter_by_event_policy


PUBLICATION_DATE = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)


def make_news(title, article_text="", description="", published_at=PUBLICATION_DATE):
    """Создаёт уже загруженный hard-кандидат для проверки event policy."""

    return {
        "title": title,
        "description": description,
        "article_text": article_text,
        "published_at": published_at,
    }


class StandaloneAttemptPolicyTests(unittest.TestCase):
    def assert_rejected_attempt(self, news_item):
        self.assertEqual(
            filter_by_event_policy([news_item], MAX_EVENT_AGE_DAYS),
            [],
        )
        self.assertEqual(
            news_item["event_policy_rejection"],
            "standalone_attempt",
        )

    def test_attempted_murder_without_death_is_rejected(self):
        self.assert_rejected_attempt(make_news(
            "Мужчину обвинили в покушении на убийство",
            "Потерпевший жив и находится в больнице.",
        ))

    def test_attempted_rape_is_rejected(self):
        self.assert_rejected_attempt(make_news(
            "Иностранец получил 9,5 года колонии за покушение на "
            "изнасилование 12-летней",
            "Девочка оказала сопротивление, и нападавший скрылся.",
        ))

    def test_rape_attempt_is_rejected(self):
        self.assert_rejected_attempt(make_news(
            "В Москве задержали мужчину за попытку изнасилования "
            "в фитнес-студии",
            "Потерпевшая вырвалась и позвала на помощь.",
        ))

    def test_serious_knife_attack_with_living_victim_is_rejected(self):
        self.assert_rejected_attempt(make_news(
            "Школьницу задержали после нападения с ножом на "
            "16-летнюю девушку",
            "Потерпевшая госпитализирована с угрожающими жизни травмами. "
            "Подростку предъявили обвинение в покушении на убийство.",
        ))

    def test_legal_attempt_construct_is_rejected(self):
        self.assert_rejected_attempt(make_news(
            "Фигуранта осудили по ч. 3 ст. 30 УК РФ",
            "Он пытался убить потерпевшего, но тот выжил.",
        ))

    def test_completed_murders_preserve_story_with_another_attempt(self):
        item = make_news(
            "Мужчина убил двух человек и покушался на убийство третьего"
        )

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS),
            [item],
        )

    def test_completed_rape_preserves_story_with_another_attempt(self):
        item = make_news(
            "Мужчину судят за преступления против двух женщин",
            "Одну женщину он изнасиловал, на изнасилование другой "
            "покушался, но она смогла убежать.",
        )

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS),
            [item],
        )

    def test_victim_who_died_after_beating_is_completed_event(self):
        item = make_news(
            "Двухлетний мальчик, избитый отцом, умер",
            "Отца ранее обвиняли в покушении на убийство ребёнка.",
        )

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS),
            [item],
        )


class StaleEventPolicyTests(unittest.TestCase):
    def assert_rejected_stale(self, news_item):
        self.assertEqual(
            filter_by_event_policy([news_item], MAX_EVENT_AGE_DAYS),
            [],
        )
        self.assertEqual(news_item["event_policy_rejection"], "stale_event")

    def test_real_agn_2002_murders_are_rejected(self):
        self.assert_rejected_stale(make_news(
            "Суд в Люберцах рассмотрит дело о трех убийствах, "
            "совершенных в 2002 году"
        ))

    def test_old_crime_with_fresh_sentence_is_rejected(self):
        self.assert_rejected_stale(make_news(
            "Суд вынес свежий приговор",
            "Преступление совершено в январе 1995 года.",
        ))

    def test_solved_old_murder_is_rejected(self):
        self.assert_rejected_stale(make_news(
            "Следователи раскрыли убийство 2003 года"
        ))

    def test_fresh_arrest_for_yesterday_murder_passes(self):
        item = make_news(
            "Подозреваемого арестовали за убийство, совершенное вчера"
        )

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS),
            [item],
        )

    def test_unknown_event_date_does_not_cause_rejection(self):
        item = make_news("Следователи расследуют убийство местного жителя")

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS),
            [item],
        )

    def test_unrelated_old_year_does_not_make_fresh_murder_stale(self):
        item = make_news(
            "Сегодня мужчину нашли убитым",
            "В 2002 году мужчина переехал в Москву. Сегодня его нашли "
            "убитым.",
        )

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS),
            [item],
        )

    def test_old_murder_named_after_case_is_rejected(self):
        self.assert_rejected_stale(make_news(
            "Сегодня задержали подозреваемого в убийстве 2002 года"
        ))

    def test_person_age_is_not_mistaken_for_event_age(self):
        item = make_news(
            "СК попросит арестовать женщину за убийство сожителя",
            "Следствие просит арестовать 31-летнюю подозреваемую.",
        )

        self.assertEqual(
            filter_by_event_policy([item], MAX_EVENT_AGE_DAYS),
            [item],
        )


if __name__ == "__main__":
    unittest.main()
