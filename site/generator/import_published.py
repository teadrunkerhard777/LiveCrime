"""Import confirmed LiveCrime publications into the site's review inbox.

This module is intentionally read-only with respect to the autoposter. It never
writes to ``storage/published.json`` and it never calls Telegram or news sites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


SITE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SITE_ROOT.parent
DEFAULT_HISTORY = PROJECT_ROOT / "storage" / "published.json"
DEFAULT_STATE = SITE_ROOT / "data" / "generator-state.json"
DEFAULT_INBOX = SITE_ROOT / "data" / "inbox"
STATE_VERSION = 1
CANDIDATE_VERSION = 1


class GeneratorError(RuntimeError):
    """Raised when intake cannot continue without risking incorrect state."""


def _read_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as error:
        raise GeneratorError(f"Файл не найден: {path}") from error
    except (json.JSONDecodeError, OSError) as error:
        raise GeneratorError(f"Не удалось безопасно прочитать JSON: {path}") from error


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


def _load_history(path: Path) -> list[dict]:
    history = _read_json(path)
    if not isinstance(history, list):
        raise GeneratorError("История публикаций должна быть JSON-массивом.")
    return history


def _validate_item(item: object, index: int) -> dict:
    if not isinstance(item, dict):
        raise GeneratorError(f"Запись истории #{index + 1} должна быть объектом.")

    title = item.get("title")
    url = item.get("url")
    if not isinstance(title, str) or not title.strip():
        raise GeneratorError(f"У записи истории #{index + 1} нет заголовка.")
    if not isinstance(url, str) or not url.strip():
        raise GeneratorError(f"У записи истории #{index + 1} нет URL.")

    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise GeneratorError(f"У записи истории #{index + 1} некорректный URL.")

    published_at = item.get("published_at")
    if published_at is not None and not isinstance(published_at, str):
        raise GeneratorError(f"У записи истории #{index + 1} некорректная дата.")

    source = item.get("source")
    if source is not None and not isinstance(source, str):
        raise GeneratorError(f"У записи истории #{index + 1} некорректный источник.")

    return item


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_id(item: dict) -> str:
    published_at = item.get("published_at") or "undated"
    date_prefix = published_at[:10] if len(published_at) >= 10 else "undated"
    url_hash = hashlib.sha256(item["url"].encode("utf-8")).hexdigest()[:12]
    return f"{date_prefix}-{url_hash}"


def _event_key(item: dict) -> str | None:
    """Return a stable key only for a complete, trustworthy event fingerprint."""

    fingerprint = item.get("event_fingerprint")
    if not isinstance(fingerprint, dict):
        return None

    canonical_fingerprint: dict[str, list[str]] = {}
    for field in ("topics", "tokens", "locations"):
        values = fingerprint.get(field)
        if not isinstance(values, list):
            return None

        normalized_values = sorted(
            {
                value.strip().casefold()
                for value in values
                if isinstance(value, str) and value.strip()
            }
        )
        if not normalized_values:
            return None
        canonical_fingerprint[field] = normalized_values

    serialized = json.dumps(
        canonical_fingerprint,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def initialize_state(history_path: Path, state_path: Path) -> dict:
    """Record the current history boundary without importing the old archive."""

    history = _load_history(history_path)
    if state_path.exists():
        state = _read_json(state_path)
        if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
            raise GeneratorError("Состояние генератора имеет неизвестный формат.")
        return state

    last_url = None
    if history:
        last_url = _validate_item(history[-1], len(history) - 1)["url"]

    state = {
        "version": STATE_VERSION,
        "history_cursor": len(history),
        "last_history_url": last_url,
        "seen_event_keys": [],
        "initialized_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _atomic_write_json(state_path, state)
    return state


def _load_state(state_path: Path, history: list[dict]) -> dict:
    state = _read_json(state_path)
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        raise GeneratorError("Состояние генератора имеет неизвестный формат.")

    cursor = state.get("history_cursor")
    if not isinstance(cursor, int) or cursor < 0:
        raise GeneratorError("В состоянии генератора указан некорректный курсор.")
    if cursor > len(history):
        raise GeneratorError("История стала короче сохранённого курсора; импорт остановлен.")
    if cursor:
        boundary_item = _validate_item(history[cursor - 1], cursor - 1)
        if boundary_item["url"] != state.get("last_history_url"):
            raise GeneratorError("История изменилась до сохранённой границы; импорт остановлен.")

    seen_event_keys = state.get("seen_event_keys", [])
    if not isinstance(seen_event_keys, list) or any(
        not isinstance(key, str) for key in seen_event_keys
    ):
        raise GeneratorError("В состоянии генератора некорректный список событий.")
    state["seen_event_keys"] = seen_event_keys

    return state


def _candidate_payload(item: dict, candidate_id: str) -> dict:
    return {
        "version": CANDIDATE_VERSION,
        "candidate_id": candidate_id,
        "section": "crime",
        "status": "needs_review",
        "imported_at": _now_iso(),
        "origin": "livecrime_published_history",
        "title": item["title"].strip(),
        "url": item["url"].strip(),
        "published_at": item.get("published_at"),
        "source": item.get("source"),
        "event_fingerprint": item.get("event_fingerprint"),
        "event_key": _event_key(item),
        "quality_gate": {
            "publishable": False,
            "reason": "Недостаточно данных для самостоятельной индексируемой страницы.",
            "missing_fields": [
                "summary",
                "event_date",
                "location",
                "legal_status",
                "source_verification",
                "channel_links",
            ],
        },
    }


def scan_new_items(
    history_path: Path,
    state_path: Path,
    inbox_path: Path,
    limit: int = 1,
) -> list[Path]:
    """Copy up to ``limit`` new confirmed publications into the review inbox."""

    if limit < 1 or limit > 10:
        raise GeneratorError("Лимит одного запуска должен быть от 1 до 10.")

    history = _load_history(history_path)
    state = _load_state(state_path, history)
    cursor = state["history_cursor"]
    selected = history[cursor : cursor + limit]
    validated = [
        _validate_item(item, cursor + offset)
        for offset, item in enumerate(selected)
    ]

    written_paths: list[Path] = []
    seen_event_keys = set(state["seen_event_keys"])
    for item in validated:
        candidate_id = _candidate_id(item)
        candidate_path = inbox_path / f"{candidate_id}.json"
        event_key = _event_key(item)
        if candidate_path.exists():
            existing = _read_json(candidate_path)
            if not isinstance(existing, dict) or existing.get("url") != item["url"]:
                raise GeneratorError(f"Конфликт файла кандидата: {candidate_path}")
            written_paths.append(candidate_path)
        elif event_key is None or event_key not in seen_event_keys:
            _atomic_write_json(
                candidate_path,
                _candidate_payload(item, candidate_id),
            )
            written_paths.append(candidate_path)

        if event_key is not None:
            seen_event_keys.add(event_key)

    if validated:
        new_cursor = cursor + len(validated)
        state["history_cursor"] = new_cursor
        state["last_history_url"] = history[new_cursor - 1]["url"]
        state["seen_event_keys"] = sorted(seen_event_keys)
        state["updated_at"] = _now_iso()
        _atomic_write_json(state_path, state)

    return written_paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Безопасно переносит новые подтверждённые публикации в очередь сайта.",
    )
    parser.add_argument(
        "--initialize",
        action="store_true",
        help="Зафиксировать текущую границу истории без импорта старого архива.",
    )
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.initialize:
            state = initialize_state(args.history, args.state)
            print(
                "Граница истории сохранена: "
                f"{state['history_cursor']} подтверждённых публикаций."
            )
            return 0

        paths = scan_new_items(
            args.history,
            args.state,
            args.inbox,
            limit=args.limit,
        )
        if not paths:
            print("Новых подтверждённых публикаций нет.")
        else:
            for path in paths:
                print(f"Кандидат ожидает проверки: {path}")
        return 0
    except GeneratorError as error:
        print(f"Импорт остановлен: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
