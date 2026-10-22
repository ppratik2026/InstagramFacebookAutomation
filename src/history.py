import json
from datetime import datetime, timezone

from .config import ROOT

HISTORY_FILE = ROOT / "data" / "history.json"


def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def recent_titles(limit: int = 60) -> list[str]:
    return [item["title"] for item in load_history()[-limit:]]


def add_entry(title: str, media_id: str | None, permalink: str | None) -> None:
    history = load_history()
    history.append({
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title": title,
        "media_id": media_id,
        "permalink": permalink,
    })
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
