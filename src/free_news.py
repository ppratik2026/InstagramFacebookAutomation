"""Free news pipeline: RSS feeds for real news + GitHub Models (free OpenAI models) for the Gujarati card text.

No paid API is needed. Inside GitHub Actions the built-in GITHUB_TOKEN (with `models: read`) is enough;
locally, use a GitHub personal access token with the "Models: read" permission as GITHUB_TOKEN.
"""
import html
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .news import IST, NewsStory

GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GujaratNewsReels/1.0)"}

# Display names for feeds that don't say who they are (WordPress feeds only give the domain).
SOURCE_NAMES = {
    "tv9gujarati.com": "TV9 Gujarati",
    "www.deshgujarat.com": "DeshGujarat",
    "www.divyabhaskar.co.in": "Divya Bhaskar",
    "www.sandesh.com": "Sandesh",
    "www.gujaratsamachar.com": "Gujarat Samachar",
}

# Google News searches (Gujarati edition) per category; "when:2d" keeps them recent.
GOOGLE_NEWS_QUERIES = {
    "crime": "ગુજરાત પોલીસ ધરપકડ",
    "good_news": "ગુજરાત ગૌરવ સિદ્ધિ",
    "government": "ગુજરાત સરકાર જાહેરાત",
}

CARD_RULES = """You write the text of one Gujarati Instagram news card for a Gujarati news page.
Write natural, simple Gujarati (Gujarati script) the way popular Gujarati news pages do: punchy and clear,
at most one or two fitting emojis per line.

Hard rules:
- Use ONLY facts that appear in the article text you are given. Never invent or guess numbers, dates, names or places.
  If the text has few facts, use fewer fact boxes rather than making any up.
- Crime stories: do not name or describe victims of sexual offences or any minor; call unconvicted people "આરોપી";
  no graphic details; no communal angle.
- Reply with JSON only."""

CARD_FORMAT = """Return a JSON object with exactly these keys:
{
  "category": "crime" | "good_news" | "government",
  "title_en": "one-line English summary",
  "kicker": "short top banner, e.g. ગુજરાત માટે મોટા સમાચાર",
  "headline": "main headline, max ~7 words, very punchy",
  "subheadline": "one line explaining the headline, max ~12 words",
  "facts": [{"label": "2-4 words", "value": "short value"}],   // 1-4 items, only real facts from the text
  "points": ["short detail line"],                            // 0-3 items
  "cta": "bottom line asking viewers to comment/share",
  "caption": "Instagram caption in Gujarati, 3-5 short lines, no hashtags",
  "hashtags": ["..."],
  "image_keywords": ["2-3 English stock-photo searches: places/objects, never real people"]
}"""


@dataclass
class FeedItem:
    title: str
    link: str
    source: str
    published: datetime
    text: str  # summary or full text from the feed (may be short)


def _strip_html(raw: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _google_news_url(query: str) -> str:
    q = urllib.parse.quote(f"{query} when:2d")
    return f"https://news.google.com/rss/search?q={q}&hl=gu&gl=IN&ceid=IN:gu"


def _read_feed(url: str) -> list[FeedItem]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except (requests.RequestException, ET.ParseError) as e:
        print(f"   Feed skipped ({url[:60]}...): {e}")
        return []

    items = []
    for node in root.iter("item"):
        title = _strip_html(node.findtext("title", ""))
        link = (node.findtext("link") or "").strip()
        try:
            published = parsedate_to_datetime(node.findtext("pubDate", ""))
        except (TypeError, ValueError):
            continue
        source_el = node.find("source")
        if source_el is not None and source_el.text:
            source = source_el.text
        else:
            domain = urllib.parse.urlparse(link).netloc
            source = SOURCE_NAMES.get(domain, domain)
        full = node.findtext(CONTENT_NS) or node.findtext("description") or ""
        if " - " in title and source and title.endswith(source):  # Google News appends " - Source"
            title = title[: -len(source)].rstrip(" -")
        if title and link:
            items.append(FeedItem(title, link, source.strip(), published, _strip_html(full)))
    return items


def _article_text(item: FeedItem) -> str:
    """Best effort: the article's paragraphs from its page, else what the feed had."""
    if "news.google.com" not in item.link:
        try:
            resp = requests.get(item.link, headers=HEADERS, timeout=30)
            if resp.ok:
                paragraphs = [_strip_html(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", resp.text, flags=re.S | re.I)]
                body = " ".join(p for p in paragraphs if len(p) > 40)
                if len(body) > len(item.text):
                    return body[:6000]
        except requests.RequestException:
            pass
    return item.text[:6000]


def _chat(cfg: dict, system: str, user: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("Missing GITHUB_TOKEN (GitHub Models). In GitHub Actions it is provided automatically.")
    last_error = None
    for model in cfg["github_models"]["models"]:
        resp = requests.post(
            GITHUB_MODELS_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
            },
            timeout=120,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        # unknown model or daily limit reached: try the next model in the list
        last_error = f"{model}: HTTP {resp.status_code} {resp.text[:300]}"
        print(f"   GitHub Models {last_error}")
    raise RuntimeError(f"All GitHub Models failed. Last error: {last_error}")


def find_story(cfg: dict, previous: list[str], category: str | None = None) -> tuple[NewsStory, str]:
    content = cfg["content"]
    wanted = [category] if category else list(content["categories"])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=content["max_news_age_hours"])

    urls = list(cfg["free"].get("feeds", []))
    urls += [_google_news_url(GOOGLE_NEWS_QUERIES[c]) for c in wanted if c in GOOGLE_NEWS_QUERIES]
    items, seen = [], set()
    for url in urls:
        for item in _read_feed(url):
            key = item.title.lower()
            if item.published >= cutoff and key not in seen:
                seen.add(key)
                items.append(item)
    if not items:
        raise RuntimeError("No recent news found in the RSS feeds.")
    items.sort(key=lambda i: i.published, reverse=True)
    items = items[:40]
    print(f"   {len(items)} recent headlines found")

    # 1) let the model pick the best story
    listing = "\n".join(
        f"{n}. [{i.source}] {i.title}{' (full text)' if len(i.text) > 400 else ''}" for n, i in enumerate(items)
    )
    pick = _chat(cfg, "You are the editor of a Gujarati Instagram news page. Reply with JSON only.", f"""
Pick the ONE headline below that is most useful or interesting for ordinary people in {content['region']}
(prices, exams, jobs, schemes, weather alerts, safety, big local achievements, major police action).
It must be about {content['region']} and fit one of these categories: {', '.join(wanted)}.
Prefer items marked (full text). Skip rumours, astrology, gossip, and anything similar to these already-posted stories:
{chr(10).join('- ' + t for t in previous) or '- (none)'}

Headlines:
{listing}

Return {{"index": <number>, "category": "<category>"}}.""")
    item = items[min(max(int(pick.get("index", 0)), 0), len(items) - 1)]
    print(f"   Picked: [{item.source}] {item.title}")

    # 2) write the card from the article text only
    article = _article_text(item)
    notes = (f"Source: {item.source}\nLink: {item.link}\nPublished: {item.published.astimezone(IST):%d %b %Y %H:%M} IST\n"
             f"Headline: {item.title}\n\nText:\n{article}")
    card = _chat(cfg, CARD_RULES, f"""{CARD_FORMAT}

Category must be one of: {', '.join(wanted)} (suggested: {pick.get('category')}).
Use exactly {content['hashtags_count']} hashtags (Gujarati and English mix).
{('Extra instructions: ' + content['extra_instructions']) if content.get('extra_instructions') else ''}

Article:
{notes}""")

    story = NewsStory(
        category=card.get("category") if card.get("category") in wanted else wanted[0],
        title_en=card.get("title_en") or item.title,
        kicker=card.get("kicker", ""),
        headline=card.get("headline") or item.title,
        subheadline=card.get("subheadline", ""),
        facts=[f for f in card.get("facts", []) if isinstance(f, dict) and f.get("label") and f.get("value")][:4],
        points=card.get("points", [])[:3],
        note="",
        layout="illustration",
        rows=[],
        cta=card.get("cta", "તમારો અભિપ્રાય કોમેન્ટમાં જણાવો 👇"),
        caption=card.get("caption", item.title),
        hashtags=card.get("hashtags", ["ગુજરાત", "GujaratNews"]),
        image_prompt="",
        image_keywords=card.get("image_keywords", ["gujarat"]),
        source_name=item.source,
        source_url=item.link,
    )
    return story, notes
