import unittest
from unittest.mock import patch

from requests import Response

from article.fetcher import (
    extract_article_image_url,
    extract_article_text,
    fetch_article_html,
)


MK_HTML = """
<html>
  <head><meta property="og:image" content="/images/crime.jpg"></head>
  <body>
    <nav><p>Главная Происшествия Политика</p></nav>
    <h1>Суд вынес приговор по делу об убийстве</h1>
    <div class="article__body" itemprop="articleBody">
      <p>Первый содержательный абзац материала MK.ru.</p>
      <p>Второй абзац с обстоятельствами уголовного дела.</p>
      <p>Читайте также:</p>
      <p>Соседняя публикация MK.ru</p>
    </div>
    <footer><p>Главный редактор и контакты редакции</p></footer>
  </body>
</html>
"""


FONTANKA_HTML = """
<html>
  <head><meta name="twitter:image" content="/images/fontanka.jpg"></head>
  <body>
    <header><p>Навигация Fontanka.ru</p></header>
    <article>
      <header><h1>Следственный комитет расследует убийство</h1></header>
      <div class="article-subheader"></div>
      <div class="content_randomHash">
        <div><p>Первый содержательный абзац статьи Фонтанки.</p></div>
        <div><p>Второй абзац с подтверждёнными обстоятельствами.</p></div>
      </div>
      <div class="related_randomHash"><p>Соседняя новость по теме</p></div>
      <div class="reactions_randomHash"><p>Лайк Смех Удивление</p></div>
    </article>
    <footer><p>Политика конфиденциальности и контакты</p></footer>
  </body>
</html>
"""


class MajorSourceExtractionTests(unittest.TestCase):
    def test_mk_uses_article_body_and_stops_before_related_links(self):
        result = extract_article_text(MK_HTML, source="MK.ru: происшествия")

        self.assertIn("Первый содержательный абзац", result)
        self.assertIn("Второй абзац", result)
        self.assertNotIn("Соседняя публикация", result)
        self.assertNotIn("Главный редактор", result)
        self.assertNotIn("Главная Происшествия", result)

    def test_fontanka_isolates_current_article_body(self):
        result = extract_article_text(
            FONTANKA_HTML,
            source="Фонтанка: происшествия",
        )

        self.assertIn("Первый содержательный абзац", result)
        self.assertIn("Второй абзац", result)
        self.assertNotIn("Соседняя новость", result)
        self.assertNotIn("Лайк Смех", result)
        self.assertNotIn("Политика конфиденциальности", result)

    def test_new_sources_keep_standard_image_metadata_extraction(self):
        self.assertEqual(
            extract_article_image_url(MK_HTML, "https://www.mk.ru/news/1"),
            "https://www.mk.ru/images/crime.jpg",
        )
        self.assertEqual(
            extract_article_image_url(
                FONTANKA_HTML,
                "https://www.fontanka.ru/2026/08/27/1/",
            ),
            "https://www.fontanka.ru/images/fontanka.jpg",
        )

    @patch("article.fetcher.requests.get")
    def test_fontanka_response_is_decoded_as_utf8(self, get_mock):
        response = Response()
        response.status_code = 200
        response._content = "Текст Фонтанки".encode("utf-8")
        response.encoding = "ISO-8859-1"
        get_mock.return_value = response

        result = fetch_article_html("https://www.fontanka.ru/2026/08/27/1/")

        self.assertEqual(result, "Текст Фонтанки")


if __name__ == "__main__":
    unittest.main()
