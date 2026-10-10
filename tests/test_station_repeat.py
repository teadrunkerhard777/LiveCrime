import copy
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from config import MAX_EVENT_AGE_DAYS
from processing.deduplicator import compare_event_fingerprints, remove_duplicates
from processing.filters import filter_by_event_policy
from storage.history import is_published


LENTA_TEXT = (
    'Sergey Elagin/Business Online\n\n'
    'Ленинский районный суд Екатеринбурга взял под стражу местного жителя '
    'Александра Гальцова, обвиненного в расправе над пенсионеркой на '
    'железнодорожной станции. Об этом «Ленте.ру» сообщили в объединенной '
    'пресс-службе судов региона.\n\nМужчина пробудет в СИЗО до 21 ноября.\n\n'
    'Пенсионерка была лишена жизни 26 апреля 2025 года на железнодорожной '
    'станции «Чапаевская». Однако тогда по горячим следам вычислить '
    'преступника не смогли. На Гальцова вышли спустя полтора года. '
    'Следствие считает его причастным к преступлению.'
)


class StationRepeatTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parent / 'fixtures' / 'ekaterinburg_station_history.json'
        self.history_item = json.loads(path.read_text(encoding='utf-8'))
        self.lenta = {
            'title': 'Предполагаемого убийцу российской пенсионерки арестовали спустя полтора года',
            'url': 'https://lenta.ru/news/2026/10/10/predpolagaemogo-ubiytsu-rossiyskoy-pensionerki-arestovali-spustya-poltora-goda/',
            'published_at': datetime.fromisoformat('2026-10-10T16:35:38+03:00'),
            'source': 'Lenta.ru', 'article_text': LENTA_TEXT,
            'strong_topics': ['убий'], 'description': '',
        }

    def test_real_repeat_matches_existing_history_without_migration(self):
        before = copy.deepcopy(self.history_item)
        result = compare_event_fingerprints(self.lenta, self.history_item)
        self.assertLess(result['token_overlap'], 0.45)
        self.assertTrue(result['lead_match'])
        self.assertTrue(is_published(self.lenta, [self.history_item]))
        self.assertEqual(before, self.history_item)
        self.assertEqual(len(remove_duplicates([self.history_item, self.lenta])), 1)

    def test_other_city_does_not_merge(self):
        self.lenta['article_text'] = LENTA_TEXT.replace('Екатеринбурга', 'Челябинска')
        self.assertFalse(is_published(self.lenta, [self.history_item]))

    def test_different_case_same_city_does_not_merge(self):
        self.lenta['title'] = 'В Екатеринбурге убили бизнесмена'
        self.lenta['article_text'] = (
            'Ленинский районный суд Екатеринбурга рассмотрел убийство бизнесмена. '
            'Его застрелили в офисе после конфликта с партнёром из-за денег.'
        )
        self.assertFalse(is_published(self.lenta, [self.history_item]))

    def test_missing_date_does_not_merge(self):
        self.lenta['published_at'] = None
        self.assertFalse(is_published(self.lenta, [self.history_item]))

    def test_real_lenta_old_event_is_rejected(self):
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [])
        self.assertEqual(self.lenta['event_policy_rejection'], 'stale_event')

    def test_previous_year_mk_event_is_rejected(self):
        self.lenta['title'] = self.history_item['title']
        self.lenta['article_text'] = (
            'Следствие полагает, что трагедия случилась 26 апреля прошлого года. '
            'Была убита местная жительница. Оперативно вычислить подозреваемого не удалось.'
        )
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [])

    def test_previous_year_background_does_not_reject_fresh_murder(self):
        self.lenta['title'] = 'В Екатеринбурге убили пенсионерку'
        self.lenta['article_text'] = (
            'Вчера пенсионерку убили на станции. '
            'С прошлого года она жила в городе. Подозреваемый арестован.'
        )
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [self.lenta])

    def test_life_deprivation_date_and_birth_year_are_distinct(self):
        self.lenta['title'] = 'Мужчину арестовали'
        self.lenta['article_text'] = 'Пенсионерка была лишена жизни 26 апреля 2025 года.'
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [])
        self.lenta['article_text'] = 'Вчера была лишена жизни пенсионерка, 1950 года рождения.'
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [self.lenta])

    def test_relative_birth_date_is_not_event_date(self):
        self.lenta['title'] = 'Вчера убили ребёнка'
        self.lenta['article_text'] = 'Убили ребёнка, 26 апреля прошлого года рождения.'
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [self.lenta])

    def test_one_and_half_years_without_numeric_date_is_stale(self):
        self.lenta['article_text'] = 'Подозреваемый найден.'
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [])

    def test_fresh_event_with_old_arrest_background_is_preserved(self):
        self.lenta['title'] = 'Мужчина убил пенсионерку вчера'
        self.lenta['article_text'] = 'Спустя полтора года после ареста он вышел на свободу.'
        self.assertEqual(filter_by_event_policy([self.lenta], MAX_EVENT_AGE_DAYS), [self.lenta])

    def test_safe_pipeline_rejects_both_and_never_sends_or_saves(self):
        import main

        mk = copy.deepcopy(self.history_item)
        mk.pop('event_fingerprint')
        mk['published_at'] = datetime.fromisoformat(mk['published_at'])
        mk['description'] = ''
        mk['article_text'] = (
            'В Екатеринбурге арестовали подозреваемого в убийстве пенсионерки. '
            'Следствие полагает, что трагедия случилась 26 апреля прошлого года. '
            'Была убита местная жительница.'
        )
        for item in (mk, self.lenta):
            item['image_url'] = None
        output = StringIO()
        with patch.object(main, 'DRY_RUN', True), \
             patch.object(main, 'collect_enabled_news', return_value=[mk, self.lenta]), \
             patch.object(main, 'filter_by_date', side_effect=lambda items, days: items), \
             patch.object(main, 'load_history', return_value=[self.history_item]), \
             patch.object(main, 'send_telegram_post') as send_text, \
             patch.object(main, 'send_telegram_photo') as send_photo, \
             patch.object(main, 'save_history') as save, \
             patch('article.fetcher.requests.get') as get, \
             redirect_stdout(output):
            main.run()
        self.assertIn('Исключено stale events: 2', output.getvalue())
        self.assertIn('Выбрано для публикации: 0', output.getvalue())
        send_text.assert_not_called()
        send_photo.assert_not_called()
        save.assert_not_called()
        get.assert_not_called()
