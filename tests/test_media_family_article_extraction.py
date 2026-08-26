import unittest

from article.fetcher import extract_article_text


MEDIA_FAMILY_SOURCES = (
    "KrasnoyarskMedia: происшествия",
    "StolicaMedia: происшествия Москвы и области",
    "AmurMedia: происшествия Хабаровского края",
    "YakutiaMedia: происшествия",
    "PriamurMedia: происшествия",
    "KamchatkaMedia: происшествия",
    "EAOMedia: происшествия",
    "MagadanMedia: происшествия",
    "ChukotkaMedia: происшествия",
)

MEDIA_FAMILY_REAL_STRUCTURE_HTML = """
<html>
  <body>
    <div class="page-fullnews px-4 exis-photo">
      <h1>Текущий материал Media-семейства</h1>
      <div class="page-content io-article-body d-block"
           itemprop="articleBody">
        <div class="page-content__related">
          <a href="/previous">Навигация на предыдущую новость</a>
        </div>
        <p>Media, 25 августа. Первый содержательный абзац статьи.</p>
        <p>Второй абзац сохраняет важные обстоятельства события.</p>
        <p>Короткий итог.</p>
        <div class="inside_banner noprint">
          <p>Рекламный блок внутри статьи</p>
        </div>
        <div class="news_links_related">
          <p><strong>ССЫЛКИ ПО ТЕМЕ:</strong></p>
          <p><a href="/related">Соседний материал Media</a></p>
        </div>
      </div>
    </div>
    <section class="neighbor-news">
      <p>Соседняя новость вне текущей статьи</p>
    </section>
    <footer>
      <p>Информация для пользователей 18+</p>
      <p>Электронный ресурс использует cookies.</p>
      <p>Политика конфиденциальности и обработки данных.</p>
      <p>На сайте используются рекомендательные технологии.</p>
      <p>© Copyright Media</p>
    </footer>
  </body>
</html>
"""


class MediaFamilyArticleExtractionTests(unittest.TestCase):
    def extract_for(self, source):
        return extract_article_text(
            MEDIA_FAMILY_REAL_STRUCTURE_HTML,
            source=source,
        )

    def test_krasnoyarskmedia_continues_to_use_clean_body(self):
        result = self.extract_for("KrasnoyarskMedia: происшествия")

        self.assertIn("Первый содержательный абзац", result)
        self.assertTrue(result.endswith("Короткий итог."))
        self.assertNotIn("cookies", result)

    def test_amurmedia_footer_is_not_included(self):
        result = self.extract_for(
            "AmurMedia: происшествия Хабаровского края"
        )

        self.assertNotIn("пользователей 18+", result)
        self.assertNotIn("Copyright", result)

    def test_yakutiamedia_footer_is_not_included(self):
        result = self.extract_for("YakutiaMedia: происшествия")

        self.assertNotIn("Политика конфиденциальности", result)
        self.assertNotIn("рекомендательные технологии", result)

    def test_priamurmedia_related_links_container_is_removed(self):
        result = self.extract_for("PriamurMedia: происшествия")

        self.assertNotIn("ССЫЛКИ ПО ТЕМЕ", result)
        self.assertNotIn("Соседний материал Media", result)

    def test_kamchatkamedia_article_body_is_preserved(self):
        result = self.extract_for("KamchatkaMedia: происшествия")

        self.assertIn("Первый содержательный абзац", result)
        self.assertIn("важные обстоятельства", result)

    def test_eaomedia_article_body_is_preserved(self):
        result = self.extract_for("EAOMedia: происшествия")

        self.assertIn("Второй абзац", result)
        self.assertIn("Короткий итог.", result)

    def test_magadanmedia_article_body_is_preserved(self):
        result = self.extract_for("MagadanMedia: происшествия")

        self.assertTrue(result.startswith("Media, 25 августа."))
        self.assertNotIn("Рекламный блок", result)

    def test_stolicamedia_footer_is_not_included(self):
        result = self.extract_for(
            "StolicaMedia: происшествия Москвы и области"
        )

        self.assertIn("Первый содержательный абзац", result)
        self.assertNotIn("cookies", result)

    def test_chukotkamedia_article_body_is_preserved(self):
        result = self.extract_for("ChukotkaMedia: происшествия")

        self.assertIn("Второй абзац", result)
        self.assertNotIn("Copyright", result)

    def test_all_confirmed_sources_remove_navigation_and_service_blocks(self):
        for source in MEDIA_FAMILY_SOURCES:
            with self.subTest(source=source):
                result = self.extract_for(source)
                self.assertNotIn("Навигация", result)
                self.assertNotIn("Рекламный блок", result)
                self.assertNotIn("Соседняя новость", result)

    def test_missing_reliable_body_returns_empty_text(self):
        html = """
        <html><body>
          <h1>Заголовок вне надёжного контейнера</h1>
          <footer><p>Контакты редакции</p></footer>
        </body></html>
        """

        for source in MEDIA_FAMILY_SOURCES:
            with self.subTest(source=source):
                self.assertEqual(
                    extract_article_text(html, source=source),
                    "",
                )

    def test_unrelated_sources_keep_generic_extraction(self):
        generic_result = extract_article_text(
            MEDIA_FAMILY_REAL_STRUCTURE_HTML
        )

        for source in (
            "АГН Москва: происшествия",
            "VN.ru: происшествия",
            "PeterburgMedia: происшествия",
            "Lenta.ru",
            "E1.ru: происшествия",
            "PrimaMedia: происшествия Приморья",
            "KrasnodarMedia: происшествия",
            "IrkutskMedia: происшествия",
            "OmskMedia: происшествия",
            "SakhalinMedia: происшествия",
        ):
            with self.subTest(source=source):
                # AGN/VN have their own strict extractors and reject this DOM.
                if source in (
                    "АГН Москва: происшествия",
                    "VN.ru: происшествия",
                ):
                    self.assertEqual(
                        extract_article_text(
                            MEDIA_FAMILY_REAL_STRUCTURE_HTML,
                            source=source,
                        ),
                        "",
                    )
                else:
                    self.assertEqual(
                        extract_article_text(
                            MEDIA_FAMILY_REAL_STRUCTURE_HTML,
                            source=source,
                        ),
                        generic_result,
                    )


if __name__ == "__main__":
    unittest.main()
