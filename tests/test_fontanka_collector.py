import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from collectors.html_collector import collect_fontanka, collect_html
from config import SOURCES


FONTANKA_LIST_HTML = """
<main>
  <div class="announcement-list">
    <div class="wrap_hash">
      <div class="content_hash">
        <div class="text-box_hash">
          <a href="/incidents/">Происшествия</a>
          <a data-announcement-title="Прямой заголовок статьи"
             href="https://www.fontanka.ru/2026/08/27/76610001/">Заголовок</a>
        </div>
      </div>
      <span>27 августа, 2026, 15:03</span>
    </div>
    <div class="wrap_hash">
      <div class="content_hash">
        <div class="text-box_hash">
          <a data-announcement-title="Статья с датой только в URL"
             href="/2026/08/26/76610002/">Вторая статья</a>
        </div>
      </div>
    </div>
    <a data-announcement-title="Служебная ссылка"
       href="/incidents/">Рубрика</a>
  </div>
</main>
"""


class FontankaCollectorTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "name": "Фонтанка: происшествия",
            "url": "https://www.fontanka.ru/incidents/",
            "timezone": "Europe/Moscow",
        }
        self.soup = BeautifulSoup(FONTANKA_LIST_HTML, "html.parser")

    def test_collects_only_direct_articles_in_common_contract(self):
        result = collect_fontanka(self.soup, self.source)

        self.assertEqual(len(result), 2)
        self.assertEqual(
            result[0],
            {
                "title": "Прямой заголовок статьи",
                "url": "https://www.fontanka.ru/2026/08/27/76610001/",
                "published_at": datetime(
                    2026,
                    8,
                    27,
                    15,
                    3,
                    tzinfo=ZoneInfo("Europe/Moscow"),
                ),
                "description": "",
                "source": "Фонтанка: происшествия",
            },
        )

    def test_uses_url_date_without_inventing_time(self):
        result = collect_fontanka(self.soup, self.source)

        self.assertEqual(
            result[1]["published_at"],
            datetime(
                2026,
                8,
                26,
                tzinfo=ZoneInfo("Europe/Moscow"),
            ),
        )

    @patch("collectors.html_collector.requests.get")
    def test_collect_html_dispatches_fontanka_adapter(self, get_mock):
        response = Mock()
        response.content = FONTANKA_LIST_HTML.encode("utf-8")
        response.raise_for_status.return_value = None
        get_mock.return_value = response
        source = {
            **self.source,
            "adapter": "fontanka",
            "limit": 40,
        }

        result = collect_html(source)

        self.assertEqual(len(result), 2)
        get_mock.assert_called_once()


class MajorSourceConfigTests(unittest.TestCase):
    def test_mk_uses_official_incident_rss(self):
        source = next(
            item for item in SOURCES
            if item["name"] == "MK.ru: происшествия"
        )

        self.assertTrue(source["enabled"])
        self.assertEqual(source["type"], "rss")
        self.assertEqual(
            source["url"],
            "https://www.mk.ru/rss/incident/index.xml",
        )

    def test_fontanka_uses_official_incident_page(self):
        source = next(
            item for item in SOURCES
            if item["name"] == "Фонтанка: происшествия"
        )

        self.assertTrue(source["enabled"])
        self.assertEqual(source["type"], "html")
        self.assertEqual(source["adapter"], "fontanka")
        self.assertEqual(source["url"], "https://www.fontanka.ru/incidents/")


if __name__ == "__main__":
    unittest.main()
