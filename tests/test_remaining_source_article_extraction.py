import unittest

from article.fetcher import extract_article_text


AMIC_HTML = """
<html><body>
  <main class="post-view">
    <div id="post" class="post">
      <h1>Текущий материал Amic.ru</h1>
      <p>Служебная подпись до статьи.</p>
      <section class="text">
        <p>Первый содержательный абзац Amic.ru.</p>
        <blockquote>Важная цитата участника события.</blockquote>
        <p>Короткий итог.</p>
        <div class="inject2">
          <p>Соседний материал Amic.ru.</p>
        </div>
      </section>
      <p>Подписка и комментарии после статьи.</p>
    </div>
  </main>
  <footer><p>Информация для пользователей 18+.</p></footer>
</body></html>
"""


A42_HTML = """
<html><body>
  <p>Данный сайт использует файлы Cookies.</p>
  <article class="material">
    <h1>Текущий материал A42</h1>
    <div class="material__body" itemprop="articleBody">
      <div class="material__card desktop-only">
        <p>Текст: редакция. Фото: A42.RU.</p>
      </div>
      <div class="material__card mobile-only">
        <p>Мобильная копия заголовка.</p>
      </div>
      <div class="rte-block rte-text">
        <p>Первый содержательный абзац A42.</p>
        <p>Второй абзац сохраняет обстоятельства события.</p>
        <p>Короткий итог.</p>
      </div>
    </div>
  </article>
  <aside><p>Подпишитесь на оперативные новости.</p></aside>
</body></html>
"""


class RemainingSourceArticleExtractionTests(unittest.TestCase):
    def test_amic_keeps_body_and_quote(self):
        result = extract_article_text(
            AMIC_HTML,
            source="Amic.ru: происшествия",
        )

        self.assertIn("Первый содержательный абзац", result)
        self.assertIn("Важная цитата", result)
        self.assertTrue(result.endswith("Короткий итог."))

    def test_amic_excludes_neighbor_and_page_chrome(self):
        result = extract_article_text(
            AMIC_HTML,
            source="Amic.ru: происшествия",
        )

        self.assertNotIn("Соседний материал", result)
        self.assertNotIn("Служебная подпись", result)
        self.assertNotIn("пользователей 18+", result)

    def test_a42_keeps_only_rte_article_text(self):
        result = extract_article_text(
            A42_HTML,
            source="A42: происшествия",
        )

        self.assertIn("Первый содержательный абзац", result)
        self.assertIn("обстоятельства события", result)
        self.assertTrue(result.endswith("Короткий итог."))

    def test_a42_excludes_cookies_author_and_subscription(self):
        result = extract_article_text(
            A42_HTML,
            source="A42: происшествия",
        )

        self.assertNotIn("Cookies", result)
        self.assertNotIn("Фото: A42", result)
        self.assertNotIn("Подпишитесь", result)
        self.assertNotIn("Мобильная копия", result)

    def test_missing_reliable_container_returns_empty_text(self):
        html = "<html><body><h1>Заголовок</h1><p>Footer</p></body></html>"

        for source in ("Amic.ru: происшествия", "A42: происшествия"):
            with self.subTest(source=source):
                self.assertEqual(
                    extract_article_text(html, source=source),
                    "",
                )

    def test_unrelated_source_keeps_generic_extraction(self):
        expected = extract_article_text(AMIC_HTML)

        self.assertEqual(
            extract_article_text(AMIC_HTML, source="Lenta.ru"),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
