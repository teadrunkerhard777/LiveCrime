"""Import public photo posts from a Telegram channel web feed."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path

CHANNEL_NAME = "RobloxHubRU"
DEFAULT_FEED_URL = f"https://t.me/s/{CHANNEL_NAME}"
SITE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTENT = SITE_ROOT / "src" / "content" / "roblox"
PHOTO_URL = re.compile(r"background-image\s*:\s*url\(['\"]?([^'\")]+)")


class RobloxImportError(RuntimeError):
    """Raised when the public feed cannot be imported safely."""


class TelegramFeedParser(HTMLParser):
    """Extract the small public contract needed from Telegram's widget HTML."""

    def __init__(self, channel_name: str = CHANNEL_NAME) -> None:
        super().__init__(convert_charrefs=True)
        self.channel_name = channel_name
        self.posts: list[dict] = []
        self.current: dict | None = None
        self.message_depth = 0
        self.text_depth: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if tag == "div" and "tgme_widget_message" in classes:
            self.current = {
                "data_post": attributes.get("data-post", ""),
                "text_parts": [],
                "image_url": None,
                "published_at": None,
            }
            self.message_depth = 1
            return

        if self.current is None:
            return

        if tag == "div":
            self.message_depth += 1
            if "tgme_widget_message_text" in classes:
                self.text_depth = self.message_depth
        elif tag == "br" and self.text_depth is not None:
            self.current["text_parts"].append("\n")
        elif "tgme_widget_message_photo_wrap" in classes:
            match = PHOTO_URL.search(attributes.get("style") or "")
            if match:
                self.current["image_url"] = html.unescape(match.group(1))
        elif tag == "time" and attributes.get("datetime"):
            self.current["published_at"] = attributes["datetime"].strip()

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.text_depth is not None:
            self.current["text_parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None or tag != "div":
            return

        if self.text_depth == self.message_depth:
            self.text_depth = None
        self.message_depth -= 1
        if self.message_depth:
            return

        data_post = self.current["data_post"]
        channel, separator, message_id = data_post.partition("/")
        text = "".join(self.current["text_parts"]).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        image_url = self.current["image_url"]
        published_at = self.current["published_at"]

        if (
            separator
            and channel.casefold() == self.channel_name.casefold()
            and message_id.isdigit()
            and text
            and isinstance(image_url, str)
            and image_url.startswith("https://")
            and published_at
        ):
            self.posts.append(
                {
                    "message_id": message_id,
                    "text": text,
                    "published_at": published_at,
                    "image_url": image_url,
                    "telegram_url": f"https://t.me/{self.channel_name}/{message_id}",
                }
            )

        self.current = None
        self.text_depth = None


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def parse_public_feed(feed_html: str, channel_name: str = CHANNEL_NAME) -> list[dict]:
    """Return photo posts while preserving Telegram text and message identity."""

    parser = TelegramFeedParser(channel_name)
    parser.feed(feed_html)
    return parser.posts


def fetch_public_feed(url: str = DEFAULT_FEED_URL) -> str:
    import requests

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; PofaktuBot/1.0)"},
            timeout=20,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as error:
        raise RobloxImportError(f"Публичная лента Telegram недоступна: {error}") from error


def import_posts(
    content_path: Path,
    limit: int = 20,
    feed_html: str | None = None,
    channel_name: str = CHANNEL_NAME,
) -> list[Path]:
    if limit < 1 or limit > 100:
        raise RobloxImportError("Лимит импорта должен быть от 1 до 100.")

    feed_url = f"https://t.me/s/{channel_name}"
    posts = parse_public_feed(
        feed_html if feed_html is not None else fetch_public_feed(feed_url),
        channel_name,
    )

    written: list[Path] = []
    for post in posts[-limit:]:
        output_path = content_path / f"{post['message_id']}.json"
        if output_path.exists():
            continue
        _atomic_write_json(output_path, post)
        written.append(output_path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Переносит фото-посты публичного Telegram-канала на сайт.")
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--channel", default=CHANNEL_NAME)
    args = parser.parse_args()

    try:
        paths = import_posts(args.content, args.limit, channel_name=args.channel)
    except RobloxImportError as error:
        print(f"Импорт @{args.channel} остановлен: {error}")
        return 1

    if not paths:
        print(f"Новых фото-постов @{args.channel} нет.")
    else:
        for path in paths:
            print(f"Добавлен пост @{args.channel}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
