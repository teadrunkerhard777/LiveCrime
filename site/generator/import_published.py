"""Import confirmed LiveCrime publications into the site.

This module is intentionally read-only with respect to the autoposter. It never
writes to ``storage/published.json`` and it never calls Telegram or news sites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


SITE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SITE_ROOT.parent
DEFAULT_HISTORY = PROJECT_ROOT / "storage" / "published.json"
DEFAULT_STATE = SITE_ROOT / "data" / "generator-state.json"
DEFAULT_INBOX = SITE_ROOT / "data" / "inbox"
DEFAULT_CONTENT = SITE_ROOT / "src" / "content" / "events"
STATE_VERSION = 1
CANDIDATE_VERSION = 1

COUNT_WORDS = (
    r"(?:дв(?:а|е|ое|ух|оих)|трое|троих|тр[её]х|четыре|четверо|четверых|"
    r"четыр[её]х|пять|пятеро|пятерых|пяти|шесть|шестеро|шестерых|шести|"
    r"семь|семеро|семерых|семи|восемь|восьмеро|восьмерых|восьми|девять|"
    r"девятеро|девятерых|девяти|десять|десятеро|десятерых|десяти)"
)
VICTIM_WORDS = (
    r"(?:человек(?:а)?|людей|женщин(?:ы)?|мужчин(?:ы)?|девоч(?:ек|ки)|"
    r"мальчик(?:ов|а)|дет(?:ей|ей)|жертв(?:ы)?|погибш(?:их|ие)|убит(?:ых|ые))"
)
EXPLICIT_MULTIPLE_VICTIMS = re.compile(
    rf"\b(?:[2-9]|[1-9]\d+)\s+{VICTIM_WORDS}\b|"
    rf"\b{COUNT_WORDS}(?:\s+[а-яё-]+){{0,2}}\s+{VICTIM_WORDS}\b|"
    rf"\bдвойн(?:ое|ого|ом)\s+убийств[оае]\b",
    re.IGNORECASE,
)
CONTENT_SOURCE_URL = re.compile(r'^\s+url:\s*["\']?(https?://[^"\'\s]+)', re.MULTILINE)
STALE_EVENT_TITLE = re.compile(
    r"\b(?:убийств|преступлен)[а-яё-]*[^.!?]{0,80}"
    r"(?:\d{1,3}[- ]?летн[а-яё-]*\s+давност[а-яё-]*|"
    r"\d{1,3}\s+(?:лет|год[а-яё-]*)\s+(?:назад|давност[а-яё-]*))",
    re.IGNORECASE,
)
ROUNDUP_TITLE = re.compile(r"\b(?:картина|итоги|обзор)\s+(?:дня|недели)\b", re.IGNORECASE)


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


def _atomic_write_text(path: Path, content: str) -> None:
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
            temporary_file.write(content)
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


def _load_existing_source_urls(content_path: Path) -> set[str]:
    """Read source URLs already represented by public or draft event cards."""

    if not content_path.exists():
        return set()

    source_urls: set[str] = set()
    for pattern in ("*.md", "*.mdx"):
        for event_path in content_path.rglob(pattern):
            try:
                content = event_path.read_text(encoding="utf-8")
            except OSError as error:
                raise GeneratorError(
                    f"Не удалось прочитать существующую карточку: {event_path}",
                ) from error
            source_urls.update(CONTENT_SOURCE_URL.findall(content))
    return source_urls


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


def is_multiple_homicide_candidate(item: dict) -> bool:
    """Keep only headlines that explicitly describe at least two homicide victims."""

    fingerprint = item.get("event_fingerprint")
    if not isinstance(fingerprint, dict):
        return False
    topics = fingerprint.get("topics")
    if not isinstance(topics, list) or "homicide" not in topics:
        return False

    title = item.get("title")
    return isinstance(title, str) and bool(EXPLICIT_MULTIPLE_VICTIMS.search(title))


def is_recent_candidate(
    item: dict,
    max_age_days: int,
    now: datetime | None = None,
) -> bool:
    """Keep only items with a reliable publication date inside the freshness window."""

    if max_age_days < 1 or max_age_days > 30:
        raise GeneratorError("Период свежести должен быть от 1 до 30 дней.")

    published_at = item.get("published_at")
    if not isinstance(published_at, str) or not published_at.strip():
        return False

    try:
        publication_date = datetime.fromisoformat(
            published_at.strip().replace("Z", "+00:00"),
        )
    except ValueError as error:
        raise GeneratorError("У кандидата некорректная дата публикации.") from error

    if publication_date.tzinfo is None:
        raise GeneratorError("Дата публикации кандидата должна содержать часовой пояс.")

    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        raise GeneratorError("Время проверки свежести должно содержать часовой пояс.")

    age = reference_time.astimezone(timezone.utc) - publication_date.astimezone(timezone.utc)
    return timedelta(0) <= age <= timedelta(days=max_age_days)


def is_current_event_candidate(item: dict) -> bool:
    """Reject headlines that explicitly describe an old event or a roundup."""

    title = item.get("title")
    if not isinstance(title, str):
        return False
    return not STALE_EVENT_TITLE.search(title) and not ROUNDUP_TITLE.search(title)


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


def _yaml_string(value: str) -> str:
    """Encode a scalar as a JSON string, which is also valid YAML."""

    return json.dumps(value, ensure_ascii=False)


def _automatic_event_content(item: dict, event_id: str) -> str:
    published_at = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
    publication_date = published_at.date().isoformat()
    source = (item.get("source") or urlparse(item["url"]).netloc).strip()
    title = item["title"].strip()
    summary = (
        f"Источник «{source}» опубликовал сообщение: «{title}». "
        "В карточке сохранены дата публикации и прямая ссылка на исходный материал."
    )
    body = (
        f"{summary}\n\n"
        "Карточка создана автоматически по подтверждённой публикации LiveCrime. "
        "Она не добавляет обстоятельств, которых нет в сохранённых данных, и ведёт "
        "к первоисточнику для ознакомления с подробностями.\n"
    )
    now = _now_iso()

    return f"""---
event_id: {_yaml_string(event_id)}
section: "crime"
publication_status: "ready"
title: {_yaml_string(title)}
summary: {_yaml_string(summary)}
event_date: {_yaml_string(publication_date)}
date_basis: "source_publication"
location:
  country: "Не указано"
  region: "Не указано"
  locality: "Место уточняется"
status: "reported"
legal_status: "not_assessed"
created_at: {_yaml_string(now)}
updated_at: {_yaml_string(now)}
topics:
  - "убийство двух и более человек"
sources:
  - name: {_yaml_string(source)}
    url: {_yaml_string(item["url"].strip())}
    published_at: {_yaml_string(item["published_at"].strip())}
updates:
  - date: {_yaml_string(publication_date)}
    title: "Опубликовано сообщение источника"
    summary: {_yaml_string(summary)}
    source_urls:
      - {_yaml_string(item["url"].strip())}
related_events: []
demo: false
---

{body}"""


def scan_new_items(
    history_path: Path,
    state_path: Path,
    inbox_path: Path,
    limit: int = 1,
    scan_limit: int | None = None,
    multiple_homicide_only: bool = False,
    max_age_days: int | None = None,
    now: datetime | None = None,
    content_path: Path = DEFAULT_CONTENT,
    publish: bool = False,
    current_event_only: bool = False,
) -> list[Path]:
    """Scan confirmed publications and create review files or public cards."""

    if limit < 1 or limit > 10:
        raise GeneratorError("Лимит одного запуска должен быть от 1 до 10.")
    if scan_limit is None:
        scan_limit = limit
    if scan_limit < limit or scan_limit > 100:
        raise GeneratorError("Лимит просмотра должен быть от лимита кандидатов до 100.")

    history = _load_history(history_path)
    state = _load_state(state_path, history)
    cursor = state["history_cursor"]
    selected = history[cursor : cursor + scan_limit]
    validated = [
        _validate_item(item, cursor + offset)
        for offset, item in enumerate(selected)
    ]

    written_paths: list[Path] = []
    seen_event_keys = set(state["seen_event_keys"])
    existing_source_urls = _load_existing_source_urls(content_path)
    processed_count = 0
    for item in validated:
        processed_count += 1
        event_key = _event_key(item)
        if item["url"] in existing_source_urls:
            if event_key is not None:
                seen_event_keys.add(event_key)
            continue
        if max_age_days is not None and not is_recent_candidate(item, max_age_days, now):
            continue
        if current_event_only and not is_current_event_candidate(item):
            continue
        if multiple_homicide_only and not is_multiple_homicide_candidate(item):
            continue

        candidate_id = _candidate_id(item)
        output_path = (
            content_path / f"{candidate_id}.md"
            if publish
            else inbox_path / f"{candidate_id}.json"
        )
        if output_path.exists():
            if publish:
                if item["url"] not in output_path.read_text(encoding="utf-8"):
                    raise GeneratorError(f"Конфликт файла карточки: {output_path}")
            else:
                existing = _read_json(output_path)
                if not isinstance(existing, dict) or existing.get("url") != item["url"]:
                    raise GeneratorError(f"Конфликт файла кандидата: {output_path}")
            written_paths.append(output_path)
        elif event_key is None or event_key not in seen_event_keys:
            if publish:
                _atomic_write_text(
                    output_path,
                    _automatic_event_content(item, candidate_id),
                )
            else:
                _atomic_write_json(
                    output_path,
                    _candidate_payload(item, candidate_id),
                )
            written_paths.append(output_path)

        if event_key is not None:
            seen_event_keys.add(event_key)

        if len(written_paths) >= limit:
            break

    if processed_count:
        new_cursor = cursor + processed_count
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
    parser.add_argument(
        "--scan-limit",
        type=int,
        help="Сколько новых записей разрешено проверить в поиске подходящего кандидата.",
    )
    parser.add_argument(
        "--multiple-homicide-only",
        action="store_true",
        help="Брать только сюжеты с явно указанными двумя или более жертвами убийства.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        help="Брать только публикации не старше указанного количества суток.",
    )
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--inbox", type=Path, default=DEFAULT_INBOX)
    parser.add_argument("--content", type=Path, default=DEFAULT_CONTENT)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Сразу создать готовую карточку сайта без ручной проверки.",
    )
    parser.add_argument(
        "--current-event-only",
        action="store_true",
        help="Не публиковать явно старые события и новостные дайджесты.",
    )
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
            scan_limit=args.scan_limit,
            multiple_homicide_only=args.multiple_homicide_only,
            max_age_days=args.max_age_days,
            content_path=args.content,
            publish=args.publish,
            current_event_only=args.current_event_only,
        )
        if not paths:
            print("Новых подтверждённых публикаций нет.")
        else:
            for path in paths:
                if args.publish:
                    print(f"Карточка опубликована: {path}")
                else:
                    print(f"Кандидат ожидает проверки: {path}")
        return 0
    except GeneratorError as error:
        print(f"Импорт остановлен: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
