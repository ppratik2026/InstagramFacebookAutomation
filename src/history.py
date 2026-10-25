import json
import re
from datetime import datetime, timedelta, timezone

from .config import ROOT

HISTORY_FILE = ROOT / "data" / "history.json"


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def recent_titles(limit: int = 60) -> list[str]:
    return [item["title"] for item in load_history()[-limit:]]


def last_category() -> str | None:
    """Category of the latest post that recorded one."""
    return next((item["category"] for item in reversed(load_history()) if item.get("category")), None)


def add_entry(title: str, media_id: str | None, permalink: str | None, category: str | None = None,
              style: dict | None = None) -> None:
    history = load_history()
    now = datetime.now(timezone.utc)
    history.append({
        "date": now.isoformat(timespec="seconds"),
        "hour": (now + timedelta(hours=5, minutes=30)).strftime("%H"),   # IST hour, for the analytics
        "title": title,
        "category": category,
        "style": style or {},
        "media_id": media_id,
        "permalink": permalink,
    })
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _key(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower()) if len(w) > 3}


def is_repeat(title_en: str, recent: list[str]) -> bool:
    """True when a story with mostly the same main words (English title) was posted recently."""
    key = _key(title_en)
    return bool(key) and any(len(key & k) / max(1, min(len(key), len(k))) >= 0.5 for k in map(_key, recent) if k)
