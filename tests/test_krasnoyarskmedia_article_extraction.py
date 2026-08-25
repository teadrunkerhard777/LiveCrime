import unittest

from article.fetcher import extract_article_text


KRASNOYARSKMEDIA_REAL_CASE_HTML = """
<html>
  <body>
    <div class="page-fullnews px-4 exis-photo">
      <h1>В Назарово муж с любовницей убили жену</h1>
      <div class="page-content io-article-body d-block"
           itemprop="articleBody">
        <p>KrasnoyarskMedia, 24 августа. Мужчина и женщина
        подозреваются в убийстве.</p>
        <p>Конфликт произошёл вечером в общежитии.</p>
        <p>Сообщники вывезли тело и спрятали его во дворе.</p>
        <p>Прохожий обнаружил тело и сообщил в полицию.</p>
        <p>Суд избрал фигурантам меру пресечения.</p>
        <div class="inside_banner noprint"></div>
        <div id="soc_invites_block" class="noprint">
          <p>Push-уведомления</p>
          <p>Главные новости от KrasnoyarskMedia в Одноклассниках</p>
          <p>Новости KrasnoyarskMedia ВКонтакте</p>
        </div>
      </div>
    </div>
    <section class="neighbor-news">
      <p>Соседняя новость с другой страницы</p>
    </section>
    <footer>
      <p>Информация для пользователей 18+</p>
      <p>Отправить сообщение в редакцию сайта?</p>
      <p>Электронный ресурс использует cookies.</p>
      <p>На сайте используются рекомендательные технологии.</p>
    </footer>
  </body>
</html>
"""


class KrasnoyarskMediaArticleExtractionTests(unittest.TestCase):
    def test_footer_and_social_invites_are_removed(self):
        result = extract_article_text(
            KRASNOYARSKMEDIA_REAL_CASE_HTML,
            source="KrasnoyarskMedia: происшествия",
        )

        self.assertNotIn("Push-уведомления", result)
        self.assertNotIn("ВКонтакте", result)
        self.assertNotIn("пользователей 18+", result)
        self.assertNotIn("cookies", result)
        self.assertNotIn("рекомендательные технологии", result)

    def test_complete_useful_article_body_is_preserved(self):
        result = extract_article_text(
            KRASNOYARSKMEDIA_REAL_CASE_HTML,
            source="KrasnoyarskMedia: происшествия",
        )

        self.assertIn("подозреваются в убийстве", result)
        self.assertIn("Конфликт произошёл", result)
        self.assertIn("вывезли тело", result)
        self.assertIn("обнаружил тело", result)
        self.assertTrue(result.endswith("меру пресечения."))

    def test_neighboring_news_is_not_included(self):
        result = extract_article_text(
            KRASNOYARSKMEDIA_REAL_CASE_HTML,
            source="KrasnoyarskMedia: происшествия",
        )

        self.assertNotIn("Соседняя новость", result)

    def test_other_sources_keep_generic_extraction(self):
        generic_result = extract_article_text(
            KRASNOYARSKMEDIA_REAL_CASE_HTML
        )

        for source in (
            "Lenta.ru",
            "PeterburgMedia: происшествия",
            "116.ru: происшествия",
            "E1.ru: происшествия",
            "vtomske.ru: происшествия",
            "IrkutskMedia: происшествия",
        ):
            with self.subTest(source=source):
                self.assertEqual(
                    extract_article_text(
                        KRASNOYARSKMEDIA_REAL_CASE_HTML,
                        source=source,
                    ),
                    generic_result,
                )

    def test_missing_reliable_body_returns_empty_text(self):
        html = """
        <html><body>
          <h1>Текущая новость</h1>
          <section class="neighbor-news">
            <p>Текст соседнего материала</p>
          </section>
          <footer><p>Контакты редакции</p></footer>
        </body></html>
        """

        result = extract_article_text(
            html,
            source="KrasnoyarskMedia: происшествия",
        )

        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
