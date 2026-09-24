import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
PAGE = (SITE_ROOT / "src/pages/about.astro").read_text(encoding="utf-8")
LAYOUT = (SITE_ROOT / "src/layouts/BaseLayout.astro").read_text(encoding="utf-8")
SITEMAP = (SITE_ROOT / "src/pages/sitemap.xml.ts").read_text(encoding="utf-8")


class AboutPageTests(unittest.TestCase):
    def test_about_page_describes_the_whole_media_hub(self):
        self.assertIn("О медиахабе", PAGE)
        self.assertIn("Roblox и Brawl Stars", PAGE)
        self.assertIn("MMA, автомобили, животных, гаджеты", PAGE)
        self.assertNotIn("Сейчас «По факту» начинается с криминальных историй", PAGE)
        self.assertNotIn("SEO изучаем", PAGE)
        self.assertNotIn("учебный проект", PAGE)
        self.assertNotIn("индексац", PAGE.lower())

    def test_about_page_links_to_live_sections_and_channels(self):
        self.assertIn('withBase("/crime/")', PAGE)
        self.assertIn('withBase("/roblox/")', PAGE)
        self.assertIn("CRIME_CHANNELS.telegram.url", PAGE)
        self.assertIn("ROBLOX_CHANNEL.max.url", PAGE)

    def test_about_page_has_search_metadata_and_structured_data(self):
        self.assertIn('"@type": "AboutPage"', PAGE)
        self.assertIn('canonicalPath="/about/"', PAGE)
        self.assertIn("title={title}", PAGE)
        self.assertIn("description={description}", PAGE)
        self.assertIn('{ path: "/about/"', SITEMAP)

    def test_about_footer_is_not_mislabeled_as_crime(self):
        self.assertIn('isAbout ? "О проекте"', LAYOUT)
        self.assertIn('href={withBase("/")}>Все темы', LAYOUT)


if __name__ == "__main__":
    unittest.main()
