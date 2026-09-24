import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
PAGE = (SITE_ROOT / "src/pages/roblox/index.astro").read_text(encoding="utf-8")
CHANNELS = (SITE_ROOT / "src/config/channels.ts").read_text(encoding="utf-8")
LAYOUT = (SITE_ROOT / "src/layouts/BaseLayout.astro").read_text(encoding="utf-8")


class RobloxPageTests(unittest.TestCase):
    def test_page_positions_itself_for_roblox_and_brawl_stars(self):
        self.assertIn("Roblox и Brawl Stars — новости и гайды", PAGE)
        self.assertIn("Свежие новости Roblox и Brawl Stars", PAGE)
        self.assertNotIn("второй раздел хаба", PAGE.lower())
        self.assertNotIn("в том же виде", PAGE.lower())
        self.assertNotIn("синхронизац", PAGE.lower())
        self.assertNotIn("публикации перенесены", LAYOUT.lower())

    def test_page_links_to_confirmed_telegram_and_max_channels(self):
        self.assertIn("https://t.me/RobloxHubRU", CHANNELS)
        self.assertIn("https://max.ru/channel_RobloxHUB", CHANNELS)
        self.assertIn("ROBLOX_CHANNEL.telegram.url", PAGE)
        self.assertIn("ROBLOX_CHANNEL.max.url", PAGE)
        self.assertIn("ROBLOX_CHANNEL.max.url", LAYOUT)


if __name__ == "__main__":
    unittest.main()
