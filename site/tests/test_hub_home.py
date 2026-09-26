import re
import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
HOME = (SITE_ROOT / "src/pages/index.astro").read_text(encoding="utf-8")
TOPICS = (SITE_ROOT / "src/config/hub-topics.ts").read_text(encoding="utf-8")
LAYOUT = (SITE_ROOT / "src/layouts/BaseLayout.astro").read_text(encoding="utf-8")
CARD = (SITE_ROOT / "src/components/HubTopicCard.astro").read_text(encoding="utf-8")


class HubHomeTests(unittest.TestCase):
    def test_home_is_a_topic_directory_not_a_crime_feed(self):
        self.assertIn("Выбирай, что интересно.", HOME)
        self.assertIn("HUB_TOPIC_GROUPS", HOME)
        self.assertNotIn('getCollection("events")', HOME)
        self.assertNotIn("EventCard", HOME)

    def test_all_requested_topics_exist_and_only_live_routes_are_linked(self):
        for title in (
            "MMA TODAY",
            "АВТО",
            "ПРЕСТУПЛЕНИЯ",
            "ROBLOX HUB",
            "ХВОСТАТЫЕ НОВОСТИ",
            "НУ И ГАДЖЕТЫ",
            "ЗВЁЗДНЫЕ БУДНИ",
        ):
            self.assertIn(title, TOPICS)

        routes = re.findall(r'url: "([^"]+)"', TOPICS)
        self.assertEqual(routes, ["/mma/", "/cars/", "/crime/", "/roblox/", "/pets/", "/gadgets/", "/stars/"])
        self.assertNotIn("ТРЕНДЫ И БРЕНДЫ", TOPICS)

    def test_home_header_is_minimal_without_changing_section_navigation(self):
        self.assertIn("Все темы", LAYOUT)
        self.assertIn('href="#themes"', LAYOUT)
        self.assertIn("Криминал", LAYOUT)
        self.assertIn("Roblox", LAYOUT)

    def test_every_topic_uses_a_local_channel_logo(self):
        images = re.findall(r'image: "(/channel-logos/[^"]+)"', TOPICS)
        self.assertEqual(len(images), 7)
        self.assertEqual(len(set(images)), 7)
        for image in images:
            self.assertTrue((SITE_ROOT / "public" / image.removeprefix("/")).is_file())

    def test_cards_keep_topic_labels_without_repeating_channel_names(self):
        self.assertIn("{topic.subtitle}", CARD)
        self.assertNotIn("<strong>{topic.title}</strong>", CARD)
        self.assertIn("topic.title", CARD)


if __name__ == "__main__":
    unittest.main()
