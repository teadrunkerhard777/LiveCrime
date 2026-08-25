import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO

from processing.deduplicator import (
    compare_event_fingerprints,
    remove_duplicates,
    title_similarity,
)
from storage.history import add_to_history, is_published


LENTA_REAL_TEXT = """
В Новосибирске вынесли приговор по делу об убийстве главы администрации
Ленинского района Александра Гриба во время охоты.

ЧП произошло 1 октября 2025 года возле села Шагалка, где чиновник вместе
со знакомым охотился на косуль. Один из охотников во время преследования
стада не убедился, что на линии огня нет других людей, и открыл огонь.
Пуля попала в Гриба, его ранение оказалось несовместимым с жизнью.

Приговор — один год принудительных работ с удержанием 10 процентов
заработной платы. Родственникам погибшего выплатят по миллиону рублей.
"""

PETERBURGMEDIA_REAL_TEXT = """
В Новосибирске вынесен приговор по делу об убийстве главы администрации
Ленинского района Александра Гриба. Трагедия произошла 1 октября 2025
года возле села Шагалка, где чиновник охотился на косуль со знакомым.

Один из участников охоты во время преследования стада не убедился, что
на линии огня нет других людей, и открыл огонь. Пуля попала в Гриба —
ранение оказалось несовместимым с жизнью.

Суд назначил осуждённому один год принудительных работ с удержанием 10%
зарплаты. С него взыскали по миллиону рублей родственникам погибшего.
"""


def make_news(
    title,
    source,
    url,
    article_text,
    published_at,
    score=10,
    strong_topics=None,
    image_url=None,
):
    """Создаёт news_item со всеми полями event comparison."""

    return {
        "title": title,
        "source": source,
        "url": url,
        "article_text": article_text,
        "description": "",
        "published_at": datetime.fromisoformat(published_at),
        "score": score,
        "strong_topics": strong_topics or ["убий"],
        "image_url": image_url,
    }


def make_real_duplicate_pair():
    """Возвращает fixture двух реальных публикаций одного события."""

    lenta = make_news(
        "Суд наказал застрелившего главу района вместо косули охотника",
        "Lenta.ru",
        (
            "https://lenta.ru/news/2026/08/25/"
            "sud-nakazal-zastrelivshego-glavu-rayona-vmesto-kosuli-"
            "ohotnika/"
        ),
        LENTA_REAL_TEXT,
        "2026-08-25T11:34:00+03:00",
        score=9,
        strong_topics=["застрел"],
    )
    peterburg = make_news(
        "Охотник получил срок за убийство чиновника в Новосибирской области",
        "PeterburgMedia: происшествия",
        "https://peterburgmedia.ru/news/2599652/",
        PETERBURGMEDIA_REAL_TEXT,
        "2026-08-25T11:46:05+10:00",
        score=11,
        strong_topics=["убий"],
        image_url="https://img.example/hunt.jpg",
    )

    return lenta, peterburg


class CrossSourceEventDeduplicationTests(unittest.TestCase):
    def test_existing_url_and_title_layers_are_preserved(self):
        first = make_news(
            "Редкий заголовок о преступлении",
            "Источник A",
            "https://example.com/same-url",
            "Первый текст.",
            "2026-08-25T10:00:00+03:00",
        )
        same_url = make_news(
            "Другой заголовок того же URL",
            "Источник B",
            "https://example.com/same-url",
            "Другой текст.",
            "2026-08-25T11:00:00+03:00",
        )
        same_title = make_news(
            first["title"],
            "Источник C",
            "https://example.com/other-url",
            "Третий текст.",
            "2026-08-25T12:00:00+03:00",
        )

        self.assertEqual(
            remove_duplicates([first, same_url, same_title]),
            [first],
        )

    def test_real_cross_source_duplicate_becomes_one_event(self):
        lenta, peterburg = make_real_duplicate_pair()

        result = remove_duplicates([lenta, peterburg])

        self.assertEqual(len(result), 1)
        self.assertIs(result[0], peterburg)

    def test_equal_score_prefers_article_with_text_and_image(self):
        lenta, peterburg = make_real_duplicate_pair()
        lenta["score"] = peterburg["score"] = 10
        lenta["image_url"] = None
        peterburg["image_url"] = "https://img.example/hunt.jpg"

        result = remove_duplicates([lenta, peterburg])

        self.assertEqual(len(result), 1)
        self.assertIs(result[0], peterburg)

    def test_real_title_similarity_explains_old_miss(self):
        lenta, peterburg = make_real_duplicate_pair()

        self.assertAlmostEqual(
            title_similarity(lenta["title"], peterburg["title"]),
            0.12598425196850394,
        )

    def test_real_duplicate_has_dense_fact_and_location_overlap(self):
        lenta, peterburg = make_real_duplicate_pair()

        details = compare_event_fingerprints(lenta, peterburg)

        self.assertTrue(details["is_duplicate"])
        self.assertIn("homicide", details["shared_topics"])
        self.assertIn("новосибирск", details["shared_locations"])
        self.assertIn("шагалк", details["shared_locations"])
        self.assertIn("александр", details["shared_tokens"])
        self.assertIn("гриб", details["shared_tokens"])
        self.assertIn("косуль", details["shared_tokens"])
        self.assertGreaterEqual(details["token_overlap"], 0.45)

    def test_debug_log_contains_event_reason(self):
        lenta, peterburg = make_real_duplicate_pair()
        output = StringIO()

        with redirect_stdout(output):
            remove_duplicates([lenta, peterburg], debug=True)

        log = output.getvalue()
        self.assertIn("[EVENT DEDUP]", log)
        self.assertIn("Source A: Lenta.ru", log)
        self.assertIn("Source B: PeterburgMedia", log)
        self.assertIn("shared tokens:", log)
        self.assertIn("topic: homicide", log)
        self.assertIn("similarity:", log)

    def test_different_murders_in_same_city_are_not_merged(self):
        first = make_news(
            "Мужчина убил знакомого в Москве",
            "Источник A",
            "https://a.example/1",
            "Иван Петров зарезал коллегу после карточной игры на Арбате.",
            "2026-08-25T10:00:00+03:00",
        )
        second = make_news(
            "Женщина убила мужа в Москве",
            "Источник B",
            "https://b.example/2",
            "Анна Сидорова отравила супруга в квартире на улице Тверской.",
            "2026-08-25T11:00:00+03:00",
        )

        self.assertEqual(len(remove_duplicates([first, second])), 2)

    def test_two_murders_on_same_day_are_not_merged(self):
        first = make_news(
            "В Петербурге убили владельца автосервиса",
            "Источник A",
            "https://a.example/3",
            "Сергея Иванова застрелили возле гаража на Лиговском проспекте.",
            "2026-08-25T08:00:00+03:00",
        )
        second = make_news(
            "В Екатеринбурге убит преподаватель",
            "Источник B",
            "https://b.example/4",
            "Алексея Смирнова нашли с ножевым ранением возле университета.",
            "2026-08-25T08:30:00+05:00",
        )

        self.assertEqual(len(remove_duplicates([first, second])), 2)

    def test_similar_procedural_titles_in_different_cities_are_not_merged(self):
        first = make_news(
            "Суд вынес приговор убийце в Казани",
            "Источник A",
            "https://a.example/5",
            "Ринат Ахметов осужден за гибель таксиста у вокзала.",
            "2026-08-25T09:00:00+03:00",
        )
        second = make_news(
            "Суд вынес приговор убийце в Москве",
            "Источник B",
            "https://b.example/6",
            "Павел Орлов осужден за гибель соседа в районе Отрадное.",
            "2026-08-25T09:30:00+03:00",
        )

        self.assertEqual(len(remove_duplicates([first, second])), 2)

    def test_event_outside_time_window_is_not_merged(self):
        lenta, peterburg = make_real_duplicate_pair()
        peterburg["published_at"] = datetime.fromisoformat(
            "2026-08-28T11:46:05+10:00"
        )

        self.assertEqual(len(remove_duplicates([lenta, peterburg])), 2)

    def test_history_fingerprint_blocks_duplicate_on_next_run(self):
        lenta, peterburg = make_real_duplicate_pair()
        history = []

        add_to_history(lenta, history)

        self.assertIn("event_fingerprint", history[0])
        self.assertTrue(is_published(peterburg, history))

    def test_legacy_history_without_fingerprint_still_uses_url_only(self):
        lenta, peterburg = make_real_duplicate_pair()
        history = [{
            "title": lenta["title"],
            "url": lenta["url"],
            "published_at": lenta["published_at"].isoformat(),
        }]

        self.assertTrue(is_published(lenta, history))
        self.assertFalse(is_published(peterburg, history))


if __name__ == "__main__":
    unittest.main()
