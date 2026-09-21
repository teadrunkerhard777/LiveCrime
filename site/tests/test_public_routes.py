import unittest
from pathlib import Path


SITE_ROOT = Path(__file__).resolve().parents[1]
PAGES_ROOT = SITE_ROOT / "src" / "pages"
FORBIDDEN_SEO_SEGMENTS = {
    "city",
    "cities",
    "location",
    "locations",
    "tag",
    "tags",
    "topic",
    "topics",
    "keyword",
    "keywords",
}
ALLOWED_DYNAMIC_PAGES = {
    Path("crime/[id].astro"),
    Path("events/[id].astro"),
}


class PublicRoutePolicyTests(unittest.TestCase):
    def test_no_city_tag_or_keyword_page_generators_exist(self):
        route_files = [
            path
            for path in PAGES_ROOT.rglob("*")
            if path.is_file() and path.suffix in {".astro", ".ts", ".js"}
        ]

        for route_file in route_files:
            relative_path = route_file.relative_to(PAGES_ROOT)
            route_segments = {
                segment.casefold()
                for part in relative_path.parts
                for segment in part.replace("[", "").replace("]", "").split(".")
            }
            self.assertTrue(
                route_segments.isdisjoint(FORBIDDEN_SEO_SEGMENTS),
                f"Запрещён автоматический SEO-маршрут: {relative_path}",
            )

    def test_only_event_pages_use_dynamic_routes(self):
        dynamic_pages = {
            path.relative_to(PAGES_ROOT)
            for path in PAGES_ROOT.rglob("*")
            if path.is_file() and "[" in path.name
        }

        self.assertEqual(dynamic_pages, ALLOWED_DYNAMIC_PAGES)


if __name__ == "__main__":
    unittest.main()
