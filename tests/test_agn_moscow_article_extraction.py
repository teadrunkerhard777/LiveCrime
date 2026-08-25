import unittest

from article.fetcher import extract_article_text


AGN_REAL_CASE_HTML = """
<html>
  <body>
    <header class="stretch mainheader">
      <div class="qr_max qr_max_video"><p><a>АГН ВИДЕО</a></p></div>
      <div class="qr_max qr_max_text"><p><a>АГН</a></p></div>
      <div class="advanced-search-popup__wrapper2">
        <p class="close-form">Закрыть</p>
      </div>
    </header>
    <main class="stretch">
      <div id="Article" class="article">
        <p class="date">10:31</p>
        <h1 class="title" itemprop="headline">
          Мужчина обвиняется в убийстве знакомого
        </h1>
        <div class="text" itemprop="articleBody">
          <p>В Волоколамске 53-летний мужчина обвиняется в убийстве
          знакомого.</p>
          <p>В ходе конфликта он нанес знакомому удар ножом в грудь.
          Потерпевший скончался.</p>
          <p>В 10:31 следователи прибыли на место преступления.</p>
          <p>Он задержан.</p>
          <p>Следователи изъяли нож и назначили судебные экспертизы.</p>
        </div>
      </div>
    </main>
    <footer>
      <p>Главный редактор информационного агентства.</p>
    </footer>
  </body>
</html>
"""


class AgnMoscowArticleExtractionTests(unittest.TestCase):
    def extract_agn(self):
        return extract_article_text(
            AGN_REAL_CASE_HTML,
            source="АГН Москва: происшествия",
        )

    def test_header_service_labels_are_removed(self):
        result = self.extract_agn()

        self.assertNotIn("АГН ВИДЕО", result)
        self.assertNotIn("\n\nАГН\n\n", f"\n\n{result}\n\n")
        self.assertNotIn("Закрыть", result)

    def test_standalone_technical_time_is_removed(self):
        result = self.extract_agn()

        self.assertFalse(result.startswith("10:31"))
        self.assertNotIn("\n\n10:31\n\n", f"\n\n{result}\n\n")

    def test_time_inside_content_paragraph_is_preserved(self):
        result = self.extract_agn()

        self.assertIn(
            "В 10:31 следователи прибыли на место преступления.",
            result,
        )

    def test_complete_article_body_and_short_paragraph_are_preserved(self):
        result = self.extract_agn()

        self.assertTrue(result.startswith("В Волоколамске 53-летний мужчина"))
        self.assertIn("удар ножом", result)
        self.assertIn("Потерпевший скончался", result)
        self.assertIn("Он задержан.", result)
        self.assertTrue(result.endswith("назначили судебные экспертизы."))

    def test_footer_and_neighboring_page_content_are_not_included(self):
        result = self.extract_agn()

        self.assertNotIn("Главный редактор", result)

    def test_other_sources_keep_their_existing_extraction(self):
        generic_result = extract_article_text(AGN_REAL_CASE_HTML)

        for source in (
            "Lenta.ru",
            "PeterburgMedia: происшествия",
            "E1.ru: происшествия",
            "vtomske.ru: происшествия",
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    extract_article_text(
                        AGN_REAL_CASE_HTML,
                        source=source,
                    ),
                    generic_result,
                )

    def test_missing_reliable_body_returns_empty_text(self):
        html = """
        <html><body>
          <header><p>АГН ВИДЕО</p></header>
          <main><p>Текст соседнего материала</p></main>
        </body></html>
        """

        result = extract_article_text(
            html,
            source="АГН Москва: происшествия",
        )

        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
