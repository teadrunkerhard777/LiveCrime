import unittest

from article.fetcher import clean_article_text, extract_article_text


VN_REAL_CASE_HTML = """
<html>
  <body>
    <main class="main-area__col-2">
      <article>
        <h1 class="det_news_title">
          Убийцу-молоточницу из Мошково помогла раскрыть директор супермаркета
        </h1>
        <div id="newstext" class="one-news-text" itemprop="articleBody">
          <div>
            Новосибирский областной суд смягчил приговор молоточнице.
            <aside class="divider dright">
              <div class="news-block-cit">
                Соседняя рекомендация про другое преступление.
              </div>
            </aside>
          </div>
          <div><br></div>
          <div>
            Женщина нанесла пенсионеру около 40 ударов молотком.
          </div>
          <div><br></div>
          <div>
            Директор супермаркета обнаружила окровавленный молоток.
          </div>
        </div>
      </article>

      <article class="one-news-left floatleft">
        <div class="news-preview-text">
          <p>13-летний мальчик отравился парами бензина.</p>
        </div>
      </article>
    </main>

    <footer>
      <p>
        © 2015 - 2026 VN.ru. Роскомнадзор. Телефон редакции.
        Политика конфиденциальности.
      </p>
    </footer>
  </body>
</html>
"""


class VnArticleExtractionTests(unittest.TestCase):
    def test_extracts_body_linked_to_current_article_title(self):
        result = extract_article_text(
            VN_REAL_CASE_HTML,
            source="VN.ru: происшествия",
        )

        self.assertIn("суд смягчил приговор молоточнице", result)
        self.assertIn("40 ударов молотком", result)
        self.assertIn("Директор супермаркета", result)

    def test_related_news_paragraph_is_not_included(self):
        result = extract_article_text(
            VN_REAL_CASE_HTML,
            source="VN.ru: происшествия",
        )

        self.assertNotIn("13-летний мальчик", result)
        self.assertNotIn("Соседняя рекомендация", result)

    def test_footer_is_not_included(self):
        extracted_text = extract_article_text(
            VN_REAL_CASE_HTML,
            source="VN.ru: происшествия",
        )
        result = clean_article_text(
            extracted_text,
            source="VN.ru: происшествия",
        )

        for footer_text in (
            "© 2015 - 2026 VN.ru",
            "Роскомнадзор",
            "Телефон редакции",
            "Политика конфиденциальности",
        ):
            self.assertNotIn(footer_text, result)

    def test_missing_reliable_body_returns_empty_text(self):
        html = """
            <article class="one-news-left">
              <p>Абзац случайной соседней новости.</p>
            </article>
            <footer><p>Служебный текст.</p></footer>
        """

        result = extract_article_text(
            html,
            source="VN.ru: происшествия",
        )

        self.assertEqual(result, "")

    def test_other_sources_keep_generic_paragraph_extraction(self):
        expected = extract_article_text(VN_REAL_CASE_HTML)

        for source in ("Lenta.ru", "АГН Москва: происшествия"):
            with self.subTest(source=source):
                result = extract_article_text(
                    VN_REAL_CASE_HTML,
                    source=source,
                )

                self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
