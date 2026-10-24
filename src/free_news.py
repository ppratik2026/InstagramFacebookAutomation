"""Free news pipeline: RSS feeds for real news + GitHub Models (free OpenAI models) for the Gujarati card text.

No paid API is needed. Inside GitHub Actions the built-in GITHUB_TOKEN (with `models: read`) is enough;
locally, use a GitHub personal access token with the "Models: read" permission as GITHUB_TOKEN.
"""
import html
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

from .card import GUJARATI_MONTHS
from .news import IST, NewsStory

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
  "stamp": "1-2 word English or Gujarati stamp for the picture, e.g. CANCELLED, BREAKING, ARRESTED, APPROVED, ALERT",
  "points": ["short detail line"],                            // 4-7 short lines, each one fact from the text
  "image_prompt": "English prompt for a dramatic illustration of the topic (objects/places, no people, no text)",
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
    category: str | None = None  # known when the item came from a per-category search


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


def _parse_json(text: str) -> dict:
    """Parse a JSON object from a model reply, tolerating code fences or text around it."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError(f"no JSON object in reply: {text[:200]!r}")
    return json.loads(text[start:end + 1])


def _post(provider: dict, key: str, model: str, messages: list, json_mode: bool) -> requests.Response:
    body = {"model": model, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json", **provider.get("headers", {})}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    # no redirects: a redirected POST silently turns into a GET and returns a useless page
    return requests.post(provider["url"], headers=headers, json=body, timeout=90, allow_redirects=False)


def _retry_after(resp: requests.Response) -> int:
    """Seconds to wait after a rate-limit reply (Retry-After header or 'Retry after 14s' in the body)."""
    match = re.search(r"[Rr]etry after (\d+)", resp.text)
    seconds = resp.headers.get("retry-after") or (match.group(1) if match else "30")
    try:
        return min(max(int(float(seconds)), 5) + 3, 90)
    except ValueError:
        return 33


def _chat(cfg: dict, system: str, user: str) -> dict:
    """Ask the first free LLM provider that works. Providers whose key isn't set are skipped."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    errors = []
    for provider in cfg["llm_providers"]:
        key = os.environ.get(provider["key_env"], "").strip() if provider.get("key_env") else ""
        if provider.get("key_env") and not key:
            continue
        for model in provider["models"]:
            for json_mode in (True, False):  # some providers reject response_format; retry without it
                resp = None
                try:
                    resp = _post(provider, key, model, messages, json_mode)
                    for _ in range(3):  # free tiers rate-limit ("1 reply every 30 seconds"): wait and retry
                        if resp.status_code not in (402, 429):
                            break
                        wait = _retry_after(resp)
                        print(f"   {provider['name']} rate limit, waiting {wait}s...")
                        time.sleep(wait)
                        resp = _post(provider, key, model, messages, json_mode)
                    if resp.status_code == 200:
                        return _parse_json(resp.json()["choices"][0]["message"]["content"])
                    problem = f"HTTP {resp.status_code}"
                except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
                    problem = f"{type(e).__name__}: {e}"
                detail = ""
                if resp is not None:
                    where = f" -> {resp.headers['location']}" if resp.headers.get("location") else ""
                    detail = f"{where} [{resp.headers.get('content-type', '?')}] {resp.text[:200]!r}"
                errors.append(f"{provider['name']} {model} (json_mode={json_mode}): {problem}{detail}")
                print(f"   LLM failed: {errors[-1]}")
                if resp is None or resp.status_code != 400:
                    break  # only a 400 is worth retrying without response_format
    if not errors:
        raise RuntimeError("No LLM provider available: add a free GROQ_API_KEY (see README).")
    raise RuntimeError("All free LLM providers failed:\n" + "\n".join(errors))


ROUNDUP = re.compile(r"\blive\b|મહત્વના સમાચાર|ટોપ ન્યૂઝ|top news|news update|headlines|સમાચાર ફટાફટ", re.I)

KICKERS = {
    "crime": "ગુજરાત ક્રાઇમ ન્યૂઝ",
    "good_news": "ગુજરાત માટે ખુશખબર",
    "government": "ગુજરાત માટે મોટા સમાચાર",
}
IMAGE_PROMPTS = {
    "crime": "police jeep with flashing red and blue lights at night on a city street in Gujarat, dramatic",
    "good_news": "Gujarat city skyline at golden sunrise with celebration fireworks, proud and hopeful",
    "government": "Gujarat government secretariat building with official documents and an announcement megaphone, dramatic light",
}
DEFAULT_HASHTAGS = ["ગુજરાત", "ગુજરાતસમાચાર", "GujaratNews", "Gujarat", "GujaratiNews",
                    "News", "BreakingNews", "Ahmedabad", "Surat", "Vadodara", "Rajkot"]


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _plain_card(item: FeedItem, category: str, article: str, hashtags_count: int) -> dict:
    """Card text taken straight from the news item, for when no AI is reachable. Adds nothing new."""
    head, rest = item.title, ""
    for sep in (":", "|", " - "):
        if sep in item.title:
            head, rest = (part.strip() for part in item.title.split(sep, 1))
            break
    sentences = [x.strip() for x in re.split(r"(?<=[.।!?])\s+", article) if len(x.strip()) > 20]
    date = item.published.astimezone(IST)
    return {
        "category": category,
        "title_en": item.title,
        "kicker": KICKERS.get(category, KICKERS["government"]),
        "headline": _shorten(head, 70),
        "subheadline": _shorten(rest or (sentences[0] if sentences else ""), 90),
        "facts": [{"label": "સ્રોત", "value": item.source},
                  {"label": "તારીખ", "value": f"{date.day} {GUJARATI_MONTHS[date.month - 1]} {date.year}"}],
        "points": [_shorten(x, 110) for x in sentences[1:6]],
        "image_prompt": IMAGE_PROMPTS.get(category, IMAGE_PROMPTS["government"]),
        "cta": "તમારો અભિપ્રાય કોમેન્ટમાં જણાવો 👇",
        "caption": _shorten(" ".join([item.title, *sentences[:2]]), 400),
        "hashtags": DEFAULT_HASHTAGS[:hashtags_count],
        "image_keywords": ["gujarat", "india news"],
    }


def find_story(cfg: dict, previous: list[str], category: str | None = None) -> tuple[NewsStory, str]:
    content = cfg["content"]
    wanted = [category] if category else list(content["categories"])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=content["max_news_age_hours"])

    sources = [(url, None) for url in cfg["free"].get("feeds", [])]
    sources += [(_google_news_url(GOOGLE_NEWS_QUERIES[c]), c) for c in wanted if c in GOOGLE_NEWS_QUERIES]
    items, seen = [], {t.lower() for t in previous}
    for url, feed_category in sources:
        for item in _read_feed(url):
            key = item.title.lower()
            if item.published >= cutoff and key not in seen:
                seen.add(key)
                item.category = feed_category
                items.append(item)
    # live blogs and "today's important news" roundups mix several stories into one page
    items = [i for i in items if not ROUNDUP.search(i.title)]
    if not items:
        raise RuntimeError("No recent news found in the RSS feeds.")
    items.sort(key=lambda i: i.published, reverse=True)
    items = items[:40]
    print(f"   {len(items)} recent headlines found")

    # 1) let the model pick the best story
    listing = "\n".join(
        f"{n}. [{i.source}] {i.title}{' (full text)' if len(i.text) > 400 else ''}" for n, i in enumerate(items)
    )
    try:
        pick = _chat(cfg, "You are the editor of a Gujarati Instagram news page. Reply with JSON only.", f"""
Pick the ONE headline below that is most useful or interesting for ordinary people in {content['region']}
(prices, exams, jobs, schemes, weather alerts, safety, big local achievements, major police action).
It must be about {content['region']} and fit one of these categories: {', '.join(wanted)}.
Prefer items marked (full text). Pick a single story, never a live blog or a list of several news.
Skip rumours, astrology, gossip, and anything similar to these already-posted stories:
{chr(10).join('- ' + t for t in previous) or '- (none)'}

Headlines:
{listing}

Return {{"index": <number>, "category": "<category>"}}.""")
        item = items[min(max(int(pick.get("index", 0)), 0), len(items) - 1)]
    except RuntimeError:
        # no AI available: take the newest story, preferring ones with full text
        print("   No AI available to pick a story, taking the newest one.")
        pick = {}
        item = next((i for i in items if len(i.text) > 400), items[0])
    print(f"   Picked: [{item.source}] {item.title}")

    # 2) write the card from the article text only
    article = _article_text(item)
    notes = (f"Source: {item.source}\nLink: {item.link}\nPublished: {item.published.astimezone(IST):%d %b %Y %H:%M} IST\n"
             f"Headline: {item.title}\n\nText:\n{article}")
    suggested = pick.get("category") or item.category or wanted[0]
    try:
        card = _chat(cfg, CARD_RULES, f"""{CARD_FORMAT}

Category must be one of: {', '.join(wanted)} (suggested: {suggested}).
Use exactly {content['hashtags_count']} hashtags (Gujarati and English mix).
{('Extra instructions: ' + content['extra_instructions']) if content.get('extra_instructions') else ''}

Article:
{notes}""")
    except RuntimeError:
        print("   No AI available to write the card, using the headline as it is.")
        card = _plain_card(item, suggested, article, content["hashtags_count"])

    story = NewsStory(
        category=card.get("category") if card.get("category") in wanted else wanted[0],
        title_en=card.get("title_en") or item.title,
        kicker=card.get("kicker", ""),
        headline=card.get("headline") or item.title,
        subheadline=card.get("subheadline", ""),
        facts=[f for f in card.get("facts", []) if isinstance(f, dict) and f.get("label") and f.get("value")][:4],
        points=[p for p in card.get("points", []) if isinstance(p, str) and p.strip()][:7],
        note="",
        layout="illustration",
        rows=[],
        cta=card.get("cta", "તમારો અભિપ્રાય કોમેન્ટમાં જણાવો 👇"),
        caption=card.get("caption", item.title),
        hashtags=card.get("hashtags", ["ગુજરાત", "GujaratNews"]),
        image_prompt=card.get("image_prompt", ""),
        stamp=card.get("stamp", ""),
        image_keywords=card.get("image_keywords", ["gujarat"]),
        source_name=item.source,
        source_url=item.link,
    )
    return story, notes
