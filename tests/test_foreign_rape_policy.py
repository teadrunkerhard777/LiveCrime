import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

from config import MAX_EVENT_AGE_DAYS
from processing.filters import filter_by_event_policy


def news(title, text):
    return {
        "title": title, "article_text": text, "description": "",
        "source": "MK.ru: происшествия", "url": "https://example.test/article",
        "published_at": datetime(2026, 10, 11, tzinfo=timezone.utc),
        "image_url": None,
    }


class ForeignRapePolicyTests(unittest.TestCase):
    def assert_rejected(self, item):
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "foreign_rape")

    def assert_kept(self, item):
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [item])

    def test_real_sweden_case_is_rejected(self):
        self.assert_rejected(news(
            "Жертва заявила об изнасиловании на улице и помогла найти подозреваемого",
            "В шведском городе Линчёпинг полиция задержала мужчину в возрасте "
            "от 50 до 59 лет по подозрению в изнасиловании женщины на улице. "
            "Предполагаемого нападавшего обнаружили в баре неподалеку.\n\n"
            "Заявление поступило 11 октября в 01:59 по местному времени.",
        ))

    def test_other_foreign_countries_are_not_sweden_only(self):
        for place in ("США", "Индии", "Франции", "Казахстане", "Японии", "Бразилии"):
            with self.subTest(place=place):
                self.assert_rejected(news("Женщину изнасиловали", f"В {place} мужчина изнасиловал женщину."))

    def test_city_without_country_is_recognized(self):
        self.assert_rejected(news("Женщину изнасиловали", "В Линчёпинге изнасиловали женщину."))

    def test_russian_case_is_kept(self):
        self.assert_kept(news("В России женщину изнасиловали", "В Москве задержали подозреваемого."))

    def test_foreign_nationality_in_russia_is_not_foreign_event(self):
        self.assert_kept(news("В Москве изнасиловали туристку из Швеции", "Потерпевшая — гражданка Швеции."))

    def test_russian_victim_abroad_is_rejected(self):
        self.assert_rejected(news("Россиянку изнасиловали в Швеции", "В Швеции задержали подозреваемого."))

    def test_unknown_location_is_explicit_and_not_assumed_foreign(self):
        item = news("Женщину изнасиловали", "На улице задержали подозреваемого.")
        self.assert_kept(item)
        self.assertEqual(item["sexual_violence_location"], "unknown")

    def test_group_rape_exception(self):
        for text in (
            "В Швеции произошло групповое изнасилование женщины.",
            "В Швеции трое мужчин изнасиловали женщину.",
            "В Швеции женщину изнасиловали два мужчины.",
            "В Швеции расследуют изнасилование женщины, совершенное группой лиц.",
        ):
            with self.subTest(text=text):
                self.assert_kept(news("Изнасилование женщины", text))

    def test_group_of_police_is_not_group_rape(self):
        self.assert_rejected(news("Женщину изнасиловали в Швеции", "Группа полицейских задержала подозреваемого."))

    def test_denied_group_rape_is_not_exception(self):
        self.assert_rejected(news("Женщину изнасиловали в Швеции", "Групповое изнасилование не подтвердилось. Действовал один мужчина."))

    def test_connected_murder_exception(self):
        for text in (
            "В Индии мужчина изнасиловал и убил девушку.",
            "В Индии девушку изнасиловали. Затем убили её.",
            "В Индии расследуют изнасилование и убийство девушки.",
            "В Индии подозреваемый обвиняется в изнасиловании и убийстве девушки.",
            "В Индии после изнасилования девушку убили.",
            "В Индии девушку убили и изнасиловали.",
        ):
            with self.subTest(text=text):
                self.assert_kept(news("Тяжёлое преступление в Индии", text))

    def test_other_murder_background_is_not_exception(self):
        self.assert_rejected(news("В Швеции женщину изнасиловали", "Подозреваемого ранее искали по другому делу об убийстве."))

    def test_uncompleted_killing_is_not_exception(self):
        self.assert_rejected(news("В Швеции женщину изнасиловали", "Мужчина изнасиловал девушку, но не убил её."))

    def test_other_topics_are_unchanged(self):
        self.assert_kept(news("В Швеции убили мужчину", "Мужчину убили на улице."))

    def test_primary_homicide_is_not_rejected_for_rape_background(self):
        self.assert_kept(news("В Швеции убили мужчину", "Мужчину убили на улице. Ранее он заявлял об изнасиловании подруги."))

    def test_foreign_place_in_related_tail_does_not_reject_domestic_event(self):
        self.assert_kept(news("В Москве женщину изнасиловали", "Полиция задержала подозреваемого.\n\nПотерпевшая жива.\n\nРанее в Швеции произошло изнасилование."))

    def test_group_exception_does_not_bypass_stale_policy(self):
        item = news("Групповое изнасилование в Швеции", "Изнасилование произошло в 2024 году.")
        self.assertEqual(filter_by_event_policy([item], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(item["event_policy_rejection"], "stale_event")

    def test_description_fallback_has_same_policy(self):
        item = news("Женщину изнасиловали", "")
        item["description"] = "В Швеции женщина сообщила об изнасиловании."
        self.assert_rejected(item)

    def test_safe_pipeline_never_sends_or_writes_history(self):
        import main

        item = news("Жертва заявила об изнасиловании на улице", "В шведском городе Линчёпинг задержали подозреваемого.")
        output = StringIO()
        with patch.object(main, "DRY_RUN", True), \
             patch.object(main, "collect_enabled_news", return_value=[item]), \
             patch.object(main, "filter_by_date", side_effect=lambda items, days: items), \
             patch.object(main, "load_history", return_value=[]), \
             patch.object(main, "send_telegram_post") as send_text, \
             patch.object(main, "send_telegram_photo") as send_photo, \
             patch.object(main, "save_history") as save, \
             patch("article.fetcher.requests.get") as get, \
             redirect_stdout(output):
            main.run()
        self.assertIn("Выбрано для публикации: 0", output.getvalue())
        self.assertIn("foreign rape", output.getvalue())
        send_text.assert_not_called()
        send_photo.assert_not_called()
        save.assert_not_called()
        get.assert_not_called()
