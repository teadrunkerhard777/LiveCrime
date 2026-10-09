import unittest
from unittest.mock import Mock, patch

from requests import Response

from article.fetcher import (
    REGIONAL_PLATFORM_DOMAINS,
    REGIONAL_PLATFORM_SOURCES,
    extract_article_text,
    fetch_article_html,
)
from collectors.html_collector import collect_html
from config import MAX_NEWS_PER_RUN, MIN_PUBLICATION_SCORE, SOURCES


class RegionalSourceTests(unittest.TestCase):
    def test_configuration_has_40_unique_enabled_sources(self):
        self.assertEqual(len(SOURCES), 40)
        self.assertTrue(all(s.get("enabled", True) for s in SOURCES))
        self.assertEqual(len({s["url"] for s in SOURCES}), 40)
        self.assertEqual(sum(s["name"] == "E1.ru: происшествия" for s in SOURCES), 1)
        self.assertEqual(MAX_NEWS_PER_RUN, 1)
        self.assertEqual(MIN_PUBLICATION_SCORE, 4)

    @patch("collectors.html_collector.requests.get")
    def test_new_cards_keep_direct_urls_dates_and_source(self, get):
        for source in (s for s in SOURCES if s.get("adapter") == "ngs"):
            with self.subTest(source=source["name"]):
                html = '''<div><a data-announcement-title="Мужчину задержали за убийство"
                href="/text/incidents/2026/10/09/12345678/">Заголовок</a>
                <span>Подозреваемого задержали</span><span>9 октября, 2026, 12:00</span>
                <a href="/text/incidents/2026/10/09/12345678/comments/">Комментарии</a>
                <a href="/text/sport/2026/10/09/12345679/">Спорт</a></div>'''
                get.return_value = Mock(content=html.encode())
                items = collect_html(source)
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["source"], source["name"])
                self.assertEqual(items[0]["url"], source["url"].split("/text/")[0] + "/text/incidents/2026/10/09/12345678/")
                self.assertIsNotNone(items[0]["published_at"].utcoffset())
                self.assertEqual(items[0]["published_at"].tzinfo.key, source["timezone"])

    @patch("collectors.html_collector.requests.get")
    def test_new_cards_respect_limit(self, get):
        source = dict(next(s for s in SOURCES if s.get("adapter") == "ngs"), limit=1)
        get.return_value = Mock(content=b'<a href="/text/incidents/2026/10/09/12345678/">One</a><a href="/text/incidents/2026/10/08/12345679/">Two</a>')
        self.assertEqual(len(collect_html(source)), 1)

    @patch("article.fetcher.requests.get")
    def test_new_platform_pages_are_utf8_even_without_http_charset(self, get):
        for domain in REGIONAL_PLATFORM_DOMAINS:
            with self.subTest(domain=domain):
                response = Response()
                response.status_code = 200
                response._content = "Кириллица статьи".encode("utf-8")
                response.encoding = "ISO-8859-1"
                get.return_value = response
                self.assertEqual(fetch_article_html(f"https://{domain}/text/incidents/1/"), "Кириллица статьи")

    def test_new_platforms_remove_photo_credits_neighbors_and_subscription(self):
        html = '''<p>Погода</p><article><h1>Новость</h1><p>Служебный lead</p>
        <div class="articleContent_hash"><figure><p>Автор / Фото</p></figure>
        <div class="uiArticleBlockText_hash"><p>Полезный текст.</p><p>Коротко.</p>
        <p>Больше новостей и даже без интернета — в нашем канале в MAX.</p>
        <p>Знаете что-то об этом ДТП? Расскажите нам!</p>
        <p>Вам известны детали произошедшего? Расскажите нам.</p></div>
        <div class="uiArticleBlockText_hash"><p>Вам есть что рассказать по этой теме? Напишите нам.</p></div>
        <aside><p>Соседняя новость</p></aside></div></article><p>Cookies</p>'''
        for source in REGIONAL_PLATFORM_SOURCES:
            with self.subTest(source=source):
                self.assertEqual(extract_article_text(html, source), "Полезный текст.\n\nКоротко.")
        # Не расширяем новый cleanup на уже работающие сайты.
        self.assertIn("нашем канале в MAX", extract_article_text(html, "116.ru: происшествия"))

    def test_northern_sources_isolate_body_from_footer_and_neighbors(self):
        bodies = {
            "БНК: новости Коми": '<div class="b-news-single"><div class="cnt daGallery">{body}</div><p>Правила комментариев</p></div>',
            "Комиинформ: новости Коми": '<div class="news-view"><div itemprop="articleBody">{body}</div><p>Соседняя новость</p></div>',
            "НАО24: новости Ненецкого округа": '<article class="fullstory"><div class="box_in"><div class="text">{body}<div class="telegram"><p>Подписка</p></div></div></div></article>',
            "СеверПост: новости Мурманской области": '<div class="c-post-block"><h1>Статья</h1><div class="uptolike-buttons"></div><hr><div>{body}</div><div><p>Подписка</p></div><div class="c-comments-block"><p>Комментарии</p></div><div><p>Соседняя новость</p></div></div>',
        }
        for source, template in bodies.items():
            with self.subTest(source=source):
                html = '<p>Навигация</p>' + template.format(body='<p>Полезный текст.</p><p>Коротко.</p>') + '<div class="cookie-banner"><p>Cookies</p></div>'
                self.assertEqual(extract_article_text(html, source), "Полезный текст.\n\nКоротко.")

    def test_missing_body_never_scrapes_page_chrome(self):
        for source in REGIONAL_PLATFORM_SOURCES + (
            "БНК: новости Коми", "Комиинформ: новости Коми",
            "СеверПост: новости Мурманской области", "НАО24: новости Ненецкого округа",
        ):
            with self.subTest(source=source):
                self.assertEqual(extract_article_text('<h1>Новость</h1><p>Footer</p>', source), "")

    def test_unrelated_source_extraction_stays_unchanged(self):
        html = '<p>Полезный текст.</p><p>Коротко.</p>'
        self.assertEqual(extract_article_text(html, "Lenta.ru"), "Полезный текст.\n\nКоротко.")
