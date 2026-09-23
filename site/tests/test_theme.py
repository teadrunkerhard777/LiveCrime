import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
LAYOUT = (SITE_ROOT / "src/layouts/BaseLayout.astro").read_text(encoding="utf-8")
STYLES = (SITE_ROOT / "src/styles/global.css").read_text(encoding="utf-8")


class ThemeTests(unittest.TestCase):
    def test_theme_toggle_is_accessible_and_persistent(self):
        self.assertIn('class="theme-toggle"', LAYOUT)
        self.assertIn('aria-label="Включить тёмную тему"', LAYOUT)
        self.assertIn('localStorage.getItem("pofaktu-theme")', LAYOUT)
        self.assertIn('localStorage.setItem("pofaktu-theme", theme)', LAYOUT)

    def test_theme_is_applied_before_body_and_updates_browser_color(self):
        head_end = LAYOUT.index("</head>")
        initial_theme_script = LAYOUT.index('localStorage.getItem("pofaktu-theme")')
        self.assertLess(initial_theme_script, head_end)
        self.assertIn('meta[name="theme-color"]', LAYOUT)

    def test_dark_palette_and_reduced_motion_are_defined(self):
        self.assertIn(':root[data-theme="dark"]', STYLES)
        self.assertIn("color-scheme: dark", STYLES)
        self.assertIn("@media (prefers-reduced-motion: reduce)", STYLES)


if __name__ == "__main__":
    unittest.main()
