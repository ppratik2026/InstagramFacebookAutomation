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
from .icons import available
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
    "www.gujaratfirst.com": "Gujarat First",
    "connectgujarat.com": "Connect Gujarat",
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
- A viewer who knows nothing about the story must understand it from the card alone. The headline must name the
  specific subject and place (e.g. "ડ્રાઇવિંગ લાયસન્સ", "અમદાવાદ", "GSEB ધોરણ 10"), never a vague word like
  "લાયસન્સ અપડેટ" or "મોટા સમાચાર". The summary answers: what happened, where, who decided/did it, who is affected.
  Every point and fact must make sense on its own (say what it is about).
- Write everything in Gujarati script. No English words except short acronyms (UPI, RBI, GSEB) and numbers.
  English terms are written in Gujarati letters: "Gold Hallmarking Center" -> "ગોલ્ડ હોલમાર્કિંગ સેન્ટર",
  "update" -> "અપડેટ". Never leave English words in Latin letters in the headline, points or facts.
- Keep it short: kicker max 4 words, summary max 2 sentences, each point max 10 words.
- Every fact value must be complete on its own: dates with month (and year if the article has it), amounts with
  ₹ and unit, counts with what they count ("21 માંગણીઓ", not "21"). Leave a fact out rather than write half of it.
- Choose the "visual" that shows this story best, like a good infographic designer:
  table = several dates/items each with a value (rates by date, district-wise numbers, schedule),
  compare = something went from one value to another (old price -> new price, before -> after),
  reasons = the story is about 3 causes / effects / benefits,
  timeline = steps or events in order, checklist = otherwise (key points).
- Reply with JSON only."""

CARD_FORMAT = """Return a JSON object with exactly these keys:
{
  "category": "crime" | "good_news" | "government",
  "title_en": "one-line English summary",
  "kicker": "short top banner, e.g. ગુજરાત માટે મોટા સમાચાર",
  "headline": "main headline, max ~8 words, punchy, naming the exact subject and place",
  "subheadline": "one line explaining the headline, max ~12 words",
  "summary": "2-3 short, simple Gujarati sentences: what happened, where, who announced/did it, who is affected",
  "facts": [{"label": "2-4 words", "value": "short value"}],   // 2-4 items (aim for 3), only real facts from the text
  "stamp": "1-2 word English or Gujarati stamp for the picture, e.g. CANCELLED, BREAKING, ARRESTED, APPROVED, ALERT",
  "mood": "breaking" | "money" | "info" | "happy",   // breaking: crime/accident/alert, money: prices/fees/salary,
                                                     // info: rules/exams/schemes/schedules, happy: good news
  "points": ["short detail line"],                            // 4-6 short self-explanatory lines, each one fact
  "visual": "table" | "compare" | "reasons" | "timeline" | "checklist",
  "rows": [{"left": "label / date", "right": "value"}],     // table or timeline: 3-6 rows, else []
  "compare": {"label": "what changed", "before": "old value", "after": "new value",
              "change": "difference, e.g. ₹12,599 ઘટાડો", "direction": "up" | "down"},   // compare only, else {}
  "reasons": [{"icon": "one of: ICON_KEYS", "text": "max 5 words"}],   // reasons: exactly 3, else []
  "highlight": "the single most striking word or number of the headline, copied exactly from it",
  "object_prompt": "English: the 1-2 main OBJECTS of the story for a cut-out 3D sticker, e.g. 'a burlap pension
                    money sack with gold coins and a calculator', 'a stack of silver bars and coins', 'a glowing light
                    bulb and an electricity tower', 'a police car with flashing lights'. Objects only, no people, no text",
  "image_prompt": "English prompt for a dramatic 3D illustration of the scene. Show what happened with generic, anonymous
                   characters (e.g. Indian police officers escorting handcuffed men seen from behind with faces hidden,
                   officials at a podium, happy families), never a real or recognisable person, no text",
  "cta": "bottom line asking viewers to comment/share",
  "caption": "Instagram caption in Gujarati, 3-5 short lines, no hashtags",
  "hashtags": ["..."],
  "image_keywords": ["2-3 English stock-photo searches: places/objects, never real people"]
}""".replace("ICON_KEYS", ", ".join(sorted(available())))


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
        title = NOISE.sub("", title).strip(" :-|,")
        if title and link:
            items.append(FeedItem(title, link, source.strip(" -|"), published, _strip_html(full)))
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
                    bad_reply = False
                except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
                    problem = f"{type(e).__name__}: {e}"
                    bad_reply = isinstance(e, ValueError) and resp is not None and resp.status_code == 200
                detail = ""
                if resp is not None:
                    where = f" -> {resp.headers['location']}" if resp.headers.get("location") else ""
                    detail = f"{where} [{resp.headers.get('content-type', '?')}] {resp.text[:200]!r}"
                errors.append(f"{provider['name']} {model} (json_mode={json_mode}): {problem}{detail}")
                print(f"   LLM failed: {errors[-1]}")
                if not bad_reply and (resp is None or resp.status_code != 400):
                    break  # a 400 or a broken JSON reply is worth one more try without response_format
    if not errors:
        raise RuntimeError("No LLM provider available: add a free GROQ_API_KEY (see README).")
    raise RuntimeError("All free LLM providers failed:\n" + "\n".join(errors))


# "Breaking News :", "Big News-" prefixes and ", જુઓ Video" style tails that news sites add to titles
NOISE = re.compile(r"^\s*(big\s+)?(breaking\s+)?news\s*[:\-–|]\s*|^\s*big\s+breaking\s*[:\-–|]?\s*"
                   r"|[,|:\-–]?\s*(જુઓ|watch)\s+(video|વીડિયો|વિડીયો)\s*$|\|\s*video\s*$", re.I)

ROUNDUP = re.compile(r"\blive\b|મહત્વના સમાચાર|ટોપ ન્યૂઝ|top news|news update|headlines|સમાચાર ફટાફટ", re.I)

KICKERS = {
    "crime": "ગુજરાત ક્રાઇમ ન્યૂઝ",
    "good_news": "ગુજરાત માટે ખુશખબર",
    "government": "ગુજરાત માટે મોટા સમાચાર",
}
IMAGE_PROMPTS = {
    "crime": "Indian police officers in khaki uniform escorting two handcuffed men seen from behind with faces hidden, "
             "police jeep with flashing red and blue lights at night on a Gujarat city street",
    "good_news": "happy Gujarati families celebrating with sweets and fireworks in front of a modern Gujarat city at sunrise",
    "government": "Indian government officials announcing a decision at a podium with microphones, citizens listening, "
                  "Gujarat secretariat building behind",
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
        "summary": _shorten(" ".join(sentences[:2]), 220),
        "points": [_shorten(x, 110) for x in sentences[2:6]],
        "image_prompt": IMAGE_PROMPTS.get(category, IMAGE_PROMPTS["government"]),
        "cta": "તમારો અભિપ્રાય કોમેન્ટમાં જણાવો 👇",
        "caption": _shorten(" ".join([item.title, *sentences[:2]]), 400),
        "hashtags": DEFAULT_HASHTAGS[:hashtags_count],
        "image_keywords": ["gujarat", "india news"],
    }


# English place names the AI sometimes leaves in the Gujarati text
PLACES = {
    "Gujarat": "ગુજરાત", "Ahmedabad": "અમદાવાદ", "Surat": "સુરત", "Vadodara": "વડોદરા", "Baroda": "વડોદરા",
    "Rajkot": "રાજકોટ", "Gandhinagar": "ગાંધીનગર", "Bhavnagar": "ભાવનગર", "Jamnagar": "જામનગર",
    "Junagadh": "જૂનાગઢ", "Kutch": "કચ્છ", "Kachchh": "કચ્છ", "Bhuj": "ભુજ", "Anand": "આણંદ", "Mehsana": "મહેસાણા",
    "Bharuch": "ભરૂચ", "Navsari": "નવસારી", "Valsad": "વલસાડ", "Vapi": "વાપી", "Morbi": "મોરબી", "Patan": "પાટણ",
    "Porbandar": "પોરબંદર", "Amreli": "અમરેલી", "Dahod": "દાહોદ", "Godhra": "ગોધરા", "Palanpur": "પાલનપુર",
    "Nadiad": "નડિયાદ", "Kheda": "ખેડા", "Botad": "બોટાદ", "Surendranagar": "સુરેન્દ્રનગર", "Himmatnagar": "હિંમતનગર",
    "Saurashtra": "સૌરાષ્ટ્ર", "Dwarka": "દ્વારકા", "Somnath": "સોમનાથ", "Gir": "ગીર",
    # months (full names first, so "September" is not read as "Sep" + "tember")
    "January": "જાન્યુઆરી", "February": "ફેબ્રુઆરી", "March": "માર્ચ", "April": "એપ્રિલ", "June": "જૂન",
    "July": "જુલાઈ", "August": "ઓગસ્ટ", "September": "સપ્ટેમ્બર", "October": "ઓક્ટોબર", "November": "નવેમ્બર",
    "December": "ડિસેમ્બર", "Jan": "જાન્યુ.", "Feb": "ફેબ્રુ.", "Mar": "માર્ચ", "Apr": "એપ્રિલ", "Jun": "જૂન",
    "Jul": "જુલાઈ", "Aug": "ઓગસ્ટ", "Sep": "સપ્ટે.", "Sept": "સપ્ટે.", "Oct": "ઓક્ટો.", "Nov": "નવે.", "Dec": "ડિસે.",
}
CARD_TEXT_FIELDS = ("kicker", "headline", "subheadline", "summary", "points", "facts", "cta", "stamp", "highlight",
                    "rows", "compare", "reasons")


def _to_gujarati(text: str) -> str:
    """English place names -> Gujarati, and stray Devanagari (Hindi) letters -> the same Gujarati letters."""
    for en, gu in PLACES.items():
        text = re.sub(rf"(?<![A-Za-z]){en}(?![A-Za-z])", gu, text, flags=re.I)   # \b fails next to Gujarati letters
    # the Gujarati Unicode block mirrors the Devanagari one, 0x180 code points later
    return "".join(chr(ord(c) + 0x180) if "\u0900" <= c <= "\u097f" and c not in "\u0964\u0965" else c for c in text)


def _gujarati_only(card: dict) -> dict:
    """Clean the text that is printed on the card (the caption keeps the AI's wording)."""
    out = dict(card)
    for key in CARD_TEXT_FIELDS:
        value = out.get(key)
        if isinstance(value, str):
            out[key] = _to_gujarati(value)
        elif key == "points" and isinstance(value, list):
            out[key] = [_to_gujarati(p) if isinstance(p, str) else p for p in value]
        elif key in ("facts", "rows", "reasons") and isinstance(value, list):
            out[key] = [{k: _to_gujarati(v) if isinstance(v, str) and k != "icon" else v for k, v in f.items()}
                        if isinstance(f, dict) else f for f in value]
        elif key == "compare" and isinstance(value, dict):
            out[key] = {k: _to_gujarati(v) if isinstance(v, str) and k != "direction" else v for k, v in value.items()}
    return out


VISUALS = ("table", "compare", "reasons", "timeline", "checklist")
MONTHS = r"જાન્યુ|ફેબ્રુ|માર્ચ|એપ્રિલ|મે|જૂન|જુલાઈ|ઓગસ્ટ|સપ્ટે|ઓક્ટો|નવે|ડિસે|આજે|આવતીકાલે|કાલે|ગઈકાલે|સોમ|મંગળ|બુધ|ગુરુ|શુક્ર|શનિ|રવિ"


def _latin_words(text: str) -> list[str]:
    """English words in Latin letters, apart from short all-caps acronyms (UPI, RBI, DGVCL)."""
    return [w for w in re.findall(r"[A-Za-z]{2,}", text or "") if not (w.isupper() and len(w) <= 6)]


def _in_gujarat(text: str) -> bool:
    places = list(PLACES.values())[:list(PLACES).index("January")] + list(PLACES)[:list(PLACES).index("January")]
    extra = ["ગુજરાત", "ગાંધીનગર", "ઉત્તર ગુજરાત", "દક્ષિણ ગુજરાત", "GSEB", "AMC", "SMC", "VMC", "RMC", "GSRTC",
             "DGVCL", "PGVCL", "MGVCL", "UGVCL", "GPSC", "GSSSB", "નર્મદા", "સાબરમતી", "તાપી", "મહીસાગર", "સાબરકાંઠા",
             "બનાસકાંઠા", "પંચમહાલ", "છોટાઉદેપુર", "અરવલ્લી", "ડાંગ", "તાપી", "દેવભૂમિ", "ગીર સોમનાથ", "વેરાવળ", "ઉના",
             "ગોંડલ", "જેતપુર", "ધોરાજી", "અંકલેશ્વર", "હાલોલ", "કલોલ", "મોડાસા", "વિસનગર", "ઊંઝા", "ડીસા", "થરાદ"]
    return any(p.lower() in text.lower() for p in places + extra)


def _incomplete(fact: dict) -> bool:
    """A date fact without month or day name, e.g. "બેઠક તારીખ: 23", says nothing on its own."""
    return bool(re.search(r"તારીખ|દિવસ|date", fact["label"], re.I)) and not re.search(MONTHS, fact["value"])


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
    # national feeds carry other states' news too: keep the stories that name a place in Gujarat
    local = [i for i in items if _in_gujarat(f"{i.title} {i.text}")]
    items = local or items
    if not items:
        raise RuntimeError("No recent news found in the RSS feeds.")
    items.sort(key=lambda i: i.published, reverse=True)
    # stories whose full article we have give much clearer cards; offer them first
    items.sort(key=lambda i: len(i.text) <= 400)
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
Strongly prefer items marked (full text): only pick one without it if no (full text) item is worth posting.
Pick a single story, never a live blog or a list of several news.
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

    card = _gujarati_only(card)
    if _latin_words(card.get("headline", "")):
        try:   # the headline is the biggest text on the card: get it fully in Gujarati script
            fixed = _chat(cfg, "You rewrite Gujarati news headlines. Reply with JSON only.", f"""
Rewrite this headline fully in Gujarati script: write English words in Gujarati letters (e.g. "Gold Hallmarking
Center" -> "ગોલ્ડ હોલમાર્કિંગ સેન્ટર"). Keep short acronyms like UPI, RBI, GSEB and all numbers as they are.
Keep the meaning and length. Also give the same for the highlight word.
Headline: {card.get("headline")}
Highlight: {card.get("highlight", "")}
Return {{"headline": "...", "highlight": "..."}}.""")
            if fixed.get("headline") and not _latin_words(fixed["headline"]):
                card["headline"], card["highlight"] = fixed["headline"], fixed.get("highlight", "")
        except RuntimeError:
            pass
    visual = card.get("visual") if card.get("visual") in VISUALS else "checklist"
    rows = [r for r in card.get("rows") or [] if isinstance(r, dict) and r.get("left") and r.get("right")][:6]
    compare = card.get("compare") if isinstance(card.get("compare"), dict) else {}
    reasons = [r for r in card.get("reasons") or [] if isinstance(r, dict) and r.get("text")][:3]
    # a layout without the data it needs falls back to the checklist
    if (visual in ("table", "timeline") and len(rows) < 2) or (visual == "compare" and not (
            compare.get("before") and compare.get("after"))) or (visual == "reasons" and len(reasons) < 3):
        visual = "checklist"
    story = NewsStory(
        category=card.get("category") if card.get("category") in wanted else wanted[0],
        title_en=card.get("title_en") or item.title,
        kicker=card.get("kicker", ""),
        headline=card.get("headline") or item.title,
        subheadline=card.get("subheadline", ""),
        facts=[f for f in card.get("facts", []) if isinstance(f, dict) and f.get("label") and f.get("value")
               and not _incomplete(f)][:4],
        points=[p for p in card.get("points", []) if isinstance(p, str) and p.strip()][:7],
        summary=card.get("summary", ""),
        note="",
        layout="illustration",
        rows=rows,
        visual=visual,
        compare=compare,
        reasons=reasons,
        highlight=card.get("highlight", "") if card.get("highlight", "") in (card.get("headline") or "") else "",
        object_prompt=card.get("object_prompt", ""),
        cta=card.get("cta", "તમારો અભિપ્રાય કોમેન્ટમાં જણાવો 👇"),
        caption=card.get("caption", item.title),
        hashtags=card.get("hashtags", ["ગુજરાત", "GujaratNews"]),
        image_prompt=card.get("image_prompt", ""),
        stamp=card.get("stamp", ""),
        mood=card.get("mood", ""),
        image_keywords=card.get("image_keywords", ["gujarat"]),
        source_name=item.source,
        source_url=item.link,
    )
    return story, notes
