import unittest

from article.fetcher import (
    PETERBURGMEDIA_STOP_MARKERS,
    clean_article_text,
)


PETERBURGMEDIA_ARTICLE_TEXT = """Осужденный на пожизненное заключение подал жалобу на отказ в переводе из колонии.

Ранее, в декабре 2025 года, суд уже рассматривал его обращение.

Александр П. отбывает наказание в исправительной колонии «Полярная сова», где находится уже 18 лет. На его счету 49 убийств, совершенных в районе Северное Бутово Москвы.

Тем временем стало известно, что дом, в котором ранее проживал он вместе с матерью, включен в программу реновации. Его мать получит новое жилье в рамках этой инициативы.

Push-уведомления

Читайте наши новости в Telegram!

Подписывайтесь на новости PeterburgMedia во ВКонтакте

Информация для пользователей 18+

Отправить сообщение в редакцию сайта?

Электронный ресурс (Сайт) использует cookies и метрические программы...

Политикой обработки персональных данных можно ознакомиться отдельно.

На сайте используются рекомендательные технологии"""


class PeterburgMediaCleanupTests(unittest.TestCase):
    def test_real_footer_is_cut_after_article_body(self):
        result = clean_article_text(
            PETERBURGMEDIA_ARTICLE_TEXT,
            source="PeterburgMedia: происшествия",
        )

        # Содержательные абзацы, включая реновацию, остаются без изменений.
        self.assertIn("Осужденный на пожизненное заключение", result)
        self.assertIn("Ранее, в декабре 2025 года", result)
        self.assertIn("На его счету 49 убийств", result)
        self.assertIn("включен в программу реновации", result)

        for service_text in (
            "Push-уведомления",
            "Telegram!",
            "Во ВКонтакте",
            "18+",
            "cookies",
            "персональных данных",
            "рекомендательные технологии",
        ):
            self.assertNotIn(service_text, result)

    def test_each_marker_stops_the_remaining_footer(self):
        for marker in PETERBURGMEDIA_STOP_MARKERS:
            with self.subTest(marker=marker):
                article_text = (
                    "Полезный абзац.\n\n"
                    f"{marker}\n\n"
                    "Служебный хвост."
                )

                result = clean_article_text(
                    article_text,
                    source="PeterburgMedia: происшествия",
                )

                self.assertEqual(result, "Полезный абзац.")

    def test_other_sources_keep_their_previous_cleanup_result(self):
        generic_result = clean_article_text(PETERBURGMEDIA_ARTICLE_TEXT)

        for source in ("Lenta.ru", "АГН Москва: происшествия"):
            with self.subTest(source=source):
                result = clean_article_text(
                    PETERBURGMEDIA_ARTICLE_TEXT,
                    source=source,
                )

                self.assertEqual(result, generic_result)
                self.assertIn("Push-уведомления", result)


if __name__ == "__main__":
    unittest.main()
