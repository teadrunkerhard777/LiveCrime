import unittest

from config import (
    CONTEXTUAL_TOPICS,
    CRIME_CONTEXT_KEYWORDS,
    EXCLUDE_KEYWORDS,
    STRONG_TOPICS,
    TOPICS,
)
from processing.filters import filter_by_topics


def make_news_item(title, description=""):
    """Создаёт минимальную новость для проверки тематического фильтра."""

    return {
        "title": title,
        "description": description,
    }


class AccusationContextTests(unittest.TestCase):
    def filter_item(self, title, description=""):
        news_item = make_news_item(title, description)

        return filter_by_topics(
            [news_item],
            TOPICS,
            EXCLUDE_KEYWORDS,
            CRIME_CONTEXT_KEYWORDS,
            STRONG_TOPICS,
            CONTEXTUAL_TOPICS,
        )

    def test_country_accusation_is_rejected(self):
        result = self.filter_item(
            "Украину обвинили в экспериментах в духовной сфере"
        )

        self.assertEqual(result, [])

    def test_political_accusation_is_rejected(self):
        result = self.filter_item("Политик обвинил оппонента во лжи")

        self.assertEqual(result, [])

    def test_formal_murder_accusation_is_accepted(self):
        result = self.filter_item(
            "Мужчине предъявили обвинение в убийстве"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_topics"], ["убий", "обвин"])

    def test_formal_accusation_phrase_supports_weak_topic(self):
        result = self.filter_item("Мужчине предъявили обвинение")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_topics"], ["обвин"])

    def test_fraud_accusation_is_accepted(self):
        result = self.filter_item(
            "Россиянина обвинили в мошенничестве"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["matched_topics"],
            ["мошеннич", "обвин"],
        )

    def test_accused_in_criminal_case_is_accepted(self):
        result = self.filter_item(
            "Обвиняемого по уголовному делу отправили под арест"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["matched_topics"],
            ["арест", "уголовн", "обвин"],
        )


class MedicalNoiseTests(unittest.TestCase):
    def filter_item(self, title, description=""):
        news_item = make_news_item(title, description)

        return filter_by_topics(
            [news_item],
            TOPICS,
            EXCLUDE_KEYWORDS,
            CRIME_CONTEXT_KEYWORDS,
            STRONG_TOPICS,
            CONTEXTUAL_TOPICS,
        )

    def test_belly_button_health_advice_is_rejected(self):
        result = self.filter_item(
            "Врач предупредил о последствиях скопления грязи в пупке"
        )

        self.assertEqual(result, [])

    def test_vitamin_deficiency_symptoms_are_rejected(self):
        result = self.filter_item(
            "Врач назвал симптомы дефицита витамина"
        )

        self.assertEqual(result, [])

    def test_doctor_suspected_of_murder_is_accepted(self):
        result = self.filter_item(
            "Врача задержали по подозрению в убийстве пациента"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["matched_topics"],
            ["убий", "задерж"],
        )

    def test_nurse_accused_of_fraud_is_accepted(self):
        result = self.filter_item(
            "Медсестру обвинили в мошенничестве"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["matched_topics"],
            ["мошеннич", "обвин"],
        )

    def test_investigation_of_death_after_attack_is_accepted(self):
        result = self.filter_item(
            "Следователи расследуют смерть пациента после нападения"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0]["matched_topics"],
            ["нападен"],
        )

    def test_weather_consequences_do_not_match_investigation_stem(self):
        result = self.filter_item(
            "Синоптик предупредил о последствиях сильного дождя"
        )

        self.assertEqual(result, [])

    def test_suicide_topic_still_matches_from_word_start(self):
        result = self.filter_item("Блогер совершил самоубийство")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_topics"], ["самоубий"])

    def test_regular_crime_material_is_accepted(self):
        result = self.filter_item(
            "Задержан подозреваемый в нападении"
        )

        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
