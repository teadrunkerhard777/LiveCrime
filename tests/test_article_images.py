import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from article.fetcher import extract_article_image_url
from main import load_selected_article_text
from scripts.test_article_images import check_image_url, run_diagnostics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = PROJECT_ROOT / "storage" / "published.json"


class ArticleImageExtractionTests(unittest.TestCase):
    def test_extracts_open_graph_image(self):
        html = """
            <meta property="og:image" content="https://img.example/main.jpg">
            <meta name="twitter:image" content="https://img.example/backup.jpg">
        """

        self.assertEqual(
            extract_article_image_url(html, "https://example.com/news/1"),
            "https://img.example/main.jpg",
        )

    def test_uses_twitter_image_as_fallback(self):
        html = """
            <meta name="twitter:image" content="https://img.example/card.jpg">
        """

        self.assertEqual(
            extract_article_image_url(html, "https://example.com/news/1"),
            "https://img.example/card.jpg",
        )

    def test_resolves_relative_image_url(self):
        html = '<meta property="og:image" content="/images/main.jpg">'

        self.assertEqual(
            extract_article_image_url(html, "https://example.com/news/1"),
            "https://example.com/images/main.jpg",
        )

    def test_returns_none_without_image_metadata(self):
        self.assertIsNone(
            extract_article_image_url(
                "<html><body><p>Текст</p></body></html>",
                "https://example.com/news/1",
            )
        )

    @patch("main.fetch_article_html")
    def test_main_uses_one_html_request_for_text_and_image(self, fetch_mock):
        fetch_mock.return_value = """
            <meta property="og:image" content="/images/main.jpg">
            <p>Основной текст статьи.</p>
        """
        news_item = {
            "title": "Новость",
            "url": "https://example.com/news/1",
        }

        load_selected_article_text([news_item])
        load_selected_article_text([news_item])

        # Повторная обработка того же news_item не загружает страницу снова.
        fetch_mock.assert_called_once_with(news_item["url"])
        self.assertEqual(news_item["article_text"], "Основной текст статьи.")
        self.assertEqual(
            news_item["image_url"],
            "https://example.com/images/main.jpg",
        )


class ImageAvailabilityTests(unittest.TestCase):
    @patch("scripts.test_article_images.requests.get")
    @patch("scripts.test_article_images.requests.head")
    def test_successful_head_does_not_download_image(self, head_mock, get_mock):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"Content-Type": "image/jpeg"}
        response.__enter__.return_value = response
        head_mock.return_value = response

        self.assertTrue(check_image_url("https://img.example/main.jpg"))
        get_mock.assert_not_called()


class ImageDiagnosticTests(unittest.TestCase):
    def test_diagnostics_do_not_change_publication_history(self):
        history_before = HISTORY_PATH.read_bytes()
        news_items = [
            {
                "title": "Тестовая новость",
                "url": "https://example.com/news/1",
            }
        ]
        html = '<meta property="og:image" content="/main.jpg">'

        with redirect_stdout(StringIO()):
            summary = run_diagnostics(
                news_items=news_items,
                fetch_html=Mock(return_value=html),
                check_image=Mock(return_value=True),
            )

        self.assertEqual(summary["checked"], 1)
        self.assertEqual(summary["found"], 1)
        self.assertEqual(summary["available"], 1)
        self.assertEqual(HISTORY_PATH.read_bytes(), history_before)


if __name__ == "__main__":
    unittest.main()
