"""Learn from the page's own numbers: which designs, colour looks, layouts, categories and hours get the most
views, so new reels use more of what works (and still try other looks now and then).

Each posted reel's style is saved in data/history.json; its Instagram insights (views, reach, shares, saves,
average watch time) are fetched into data/stats.json, and data/report.md gives a readable summary.
"""
import json
import random
from collections import defaultdict
from datetime import datetime, timezone

import requests

from .config import ROOT
from .history import load_history

STATS_FILE = ROOT / "data" / "stats.json"
REPORT_FILE = ROOT / "data" / "report.md"
METRICS = "views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time"
MIN_AGE_HOURS = 6        # younger reels are still growing; they are not compared yet
DIMENSIONS = ["design", "palette", "visual", "category", "mood", "music", "hour"]


def load_stats() -> dict:
    return json.loads(STATS_FILE.read_text(encoding="utf-8")) if STATS_FILE.exists() else {}


def update_stats(token: str, api_version: str = "v21.0", max_posts: int = 150) -> dict:
    """Fetch insights for the recent posts (old enough to compare) and save them."""
    stats = load_stats()
    now = datetime.now(timezone.utc)
    for post in load_history()[-max_posts:]:
        media_id = post.get("media_id")
        if not media_id:
            continue
        age = (now - datetime.fromisoformat(post["date"])).total_seconds() / 3600
        if age < MIN_AGE_HOURS:
            continue
        try:
            resp = requests.get(f"https://graph.instagram.com/{api_version}/{media_id}/insights",
                                params={"metric": METRICS, "access_token": token}, timeout=30)
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue
        if resp.status_code != 200:
            print(f"   Insights for {media_id} failed: {str(data)[:150]}")
            continue
        values = {m["name"]: m["values"][0]["value"] for m in data.get("data", []) if m.get("values")}
        stats[media_id] = {**values, "age_hours": round(age, 1), "updated": now.isoformat(timespec="seconds")}
    STATS_FILE.write_text(json.dumps(stats, indent=1) + "\n", encoding="utf-8")
    write_report(stats)
    return stats


def _score(values: dict) -> float:
    """One number per reel: views, with shares and saves (strong signals for the algorithm) weighted up."""
    return values.get("views", 0) + 20 * values.get("shares", 0) + 10 * values.get("saved", 0) \
        + 5 * values.get("comments", 0) + 2 * values.get("likes", 0)


def performance() -> dict[str, dict[str, tuple[float, int]]]:
    """For each style dimension: value -> (score relative to the page average, number of reels)."""
    stats = load_stats()
    rows = [(post, _score(stats[post["media_id"]])) for post in load_history() if post.get("media_id") in stats]
    if not rows:
        return {}
    average = sum(score for _, score in rows) / len(rows) or 1.0
    result: dict[str, dict[str, tuple[float, int]]] = {}
    for dim in DIMENSIONS:
        groups = defaultdict(list)
        for post, score in rows:
            value = (post.get("style") or {}).get(dim) if dim not in ("category", "hour") else post.get(dim)
            if value:
                groups[str(value)].append(score)
        result[dim] = {v: (sum(s) / len(s) / average, len(s)) for v, s in groups.items()}
    return result


def weighted_choice(options: list[str], dimension: str, explore: float = 0.3, min_posts: int = 3) -> str:
    """Pick among options, favouring the ones whose reels did better on this page. With little data (or now
    and then, to keep testing new looks) the pick is random."""
    if not options:
        raise ValueError("no options")
    perf = performance().get(dimension, {})
    known = {o: perf[o][0] for o in options if o in perf and perf[o][1] >= min_posts}
    if not known or random.random() < explore:
        return random.choice(options)
    # untested options get an average chance; tested ones their measured strength (squared, to lean on winners)
    weights = [max(0.05, known.get(o, 1.0)) ** 2 for o in options]
    return random.choices(options, weights=weights)[0]


def write_report(stats: dict | None = None) -> None:
    """data/report.md: the best and worst reels and which styles work, for people to read."""
    stats = stats if stats is not None else load_stats()
    posts = [(p, stats[p["media_id"]]) for p in load_history() if p.get("media_id") in stats]
    if not posts:
        return
    posts.sort(key=lambda item: _score(item[1]), reverse=True)
    lines = [f"# Page report ({datetime.now(timezone.utc):%d %b %Y %H:%M} UTC)", "",
             f"{len(posts)} reels compared (older than {MIN_AGE_HOURS} hours).", "", "## Top reels", "",
             "| Views | Reach | Shares | Saves | Category | Design | Title |", "|---|---|---|---|---|---|---|"]
    for post, v in posts[:10]:
        lines.append(f"| {v.get('views', 0)} | {v.get('reach', 0)} | {v.get('shares', 0)} | {v.get('saved', 0)} | "
                     f"{post.get('category', '')} | {(post.get('style') or {}).get('design', '')} | "
                     f"[{post['title']}]({post.get('permalink', '')}) |")
    for dim, values in performance().items():
        if not values:
            continue
        lines += ["", f"## {dim}", "", "| Value | Strength (1 = page average) | Reels |", "|---|---|---|"]
        for value, (strength, n) in sorted(values.items(), key=lambda kv: -kv[1][0]):
            lines.append(f"| {value} | {strength:.2f} | {n} |")
    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
