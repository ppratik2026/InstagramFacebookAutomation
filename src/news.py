"""Find a real, recent Gujarat news story with Gemini + Google Search, then turn it into card content."""
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from google import genai
from google.genai import types

IST = timezone(timedelta(hours=5, minutes=30))

RESEARCH_RULES = """You are a news researcher for a Gujarati Instagram news page.
Use Google Search to find ONE real, verifiable news story. Prefer established outlets
(Divya Bhaskar, Sandesh, Gujarat Samachar, TV9 Gujarati, ABP Asmita, News18 Gujarati,
Times of India, Indian Express, DeshGujarat, official gujarat.gov.in / gseb.org pages).

Hard rules:
- Never invent or guess facts, numbers, dates or names. Everything must come from the sources you read.
- Prefer stories confirmed by at least two sources, or by one official source.
- Crime stories: do not name or describe victims of sexual offences or any minor; call unconvicted people
  "accused"; no graphic details; no communal angle.
- Skip rumours, unverified viral claims and anything older than the allowed age."""

FORMAT_RULES = """You turn research notes into the text of one Gujarati Instagram news card.
Write in natural, simple Gujarati (Gujarati script) the way popular Gujarati news pages do: punchy, clear,
one or two fitting emojis at most per line. Use only facts present in the notes. Keep numbers and dates exact.
Crime stories: neutral wording, "આરોપી" for the accused, no victim identities, nothing graphic."""

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["crime", "good_news", "government"]},
        "title_en": {"type": "string", "description": "One-line English summary, used to avoid repeat posts."},
        "kicker": {"type": "string", "description": "Short top banner, e.g. 'ગુજરાત માટે મોટા સમાચાર'."},
        "headline": {"type": "string", "description": "Main headline, max ~7 words, very punchy."},
        "subheadline": {"type": "string", "description": "One line that explains the headline, max ~12 words."},
        "facts": {
            "type": "array",
            "description": "2-4 key facts shown as boxes.",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "2-4 words, e.g. 'લાગુ તારીખ'."},
                    "value": {"type": "string", "description": "Short value, e.g. '1 જુલાઈ 2026'."},
                },
                "required": ["label", "value"],
            },
        },
        "points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-4 short Gujarati lines with more detail: why it happened, who is affected, what to do next.",
        },
        "note": {
            "type": "string",
            "description": "Optional one-line Gujarati disclaimer (e.g. prices may vary by city), or empty string.",
        },
        "layout": {
            "type": "string",
            "enum": ["illustration", "list"],
            "description": (
                "'list' when the news is mainly a schedule or list (dates, districts, timings, rates per item); "
                "'illustration' for everything else."
            ),
        },
        "rows": {
            "type": "array",
            "description": "For layout 'list': 3-11 rows shown as a colourful table (e.g. day -> districts). Empty otherwise.",
            "items": {
                "type": "object",
                "properties": {
                    "left": {"type": "string", "description": "Short key, e.g. 'સોમવાર' or '5 નવેમ્બર'."},
                    "right": {"type": "string", "description": "The value, e.g. 'ગાંધીનગર, વલસાડ'."},
                },
                "required": ["left", "right"],
            },
        },
        "cta": {"type": "string", "description": "Bottom line asking viewers to comment/share."},
        "caption": {"type": "string", "description": "Instagram caption in Gujarati, 3-5 short lines summarising the news, no hashtags."},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "image_prompt": {
            "type": "string",
            "description": (
                "English prompt for an AI background illustration of the news topic: vivid, dramatic, "
                "news-thumbnail style, objects and places only. No text, letters, logos, flags of parties, "
                "or recognisable real people."
            ),
        },
        "image_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-3 English stock-photo searches for a backup background (places/objects, never real people).",
        },
        "source_name": {"type": "string"},
        "source_url": {"type": "string"},
    },
    "required": [
        "category", "title_en", "kicker", "headline", "subheadline", "facts", "points", "note", "layout", "rows", "cta",
        "caption", "hashtags", "image_prompt", "image_keywords", "source_name", "source_url",
    ],
}


@dataclass
class NewsStory:
    category: str
    title_en: str
    kicker: str
    headline: str
    subheadline: str
    facts: list[dict]
    points: list[str]
    note: str
    layout: str
    rows: list[dict]
    cta: str
    caption: str
    hashtags: list[str]
    image_prompt: str
    image_keywords: list[str]
    source_name: str
    source_url: str
    stamp: str = ""  # short stamp on the picture, e.g. "CANCELLED"
    summary: str = ""  # 2-3 sentence plain explanation of the story
    mood: str = ""  # breaking / money / info / happy: picks the design, stickers and colours
    visual: str = ""  # bulletin layout: table / compare / reasons / timeline / checklist
    compare: dict = field(default_factory=dict)  # before -> after: label, before, after, change, direction
    reasons: list = field(default_factory=list)  # [{"icon": key, "text": ...}] for the reasons row
    highlight: str = ""  # the one word or number of the headline printed extra big
    object_prompt: str = ""  # main object(s) of the story, drawn as a cut-out for the bulletin design
    person: str = ""  # English Wikipedia name of the public figure the story is about (their real photo is used)
    photo_credit: str = ""  # set when a real photo is used: shown instead of "symbolic picture"
    style: dict = field(default_factory=dict)  # how the reel looked (design, palette, ...), saved for the analytics

    def full_caption(self) -> str:
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in self.hashtags)
        return f"{self.caption}\n\nસ્રોત: {self.source_name}\n\n{tags}".strip()


def _research(client: genai.Client, cfg: dict, previous: list[str], category: str | None) -> str:
    content = cfg["content"]
    now = datetime.now(IST)
    categories = content["categories"]
    wanted = {category: categories[category]} if category else categories

    prompt = f"""Today is {now:%A, %d %B %Y}, {now:%H:%M} IST.

Find one important {content['region']} news story published in the last {content['max_news_age_hours']} hours
from one of these categories:
""" + "\n".join(f"- {key}: {desc}" for key, desc in wanted.items()) + """

Pick the story most useful or interesting for ordinary people in Gujarat (prices, exams, jobs, schemes,
weather alerts, safety, big local achievements, major police action).
"""
    if previous:
        prompt += "\nAlready posted, do not pick these again:\n" + "\n".join(f"- {t}" for t in previous) + "\n"
    if content.get("extra_instructions"):
        prompt += f"\nExtra instructions: {content['extra_instructions']}\n"
    prompt += """
Reply with research notes: the category, what happened, where, when, all key numbers/dates,
who announced it, and the source names with URLs and publish dates."""

    response = client.models.generate_content(
        model=cfg["gemini"]["text_model"],
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=RESEARCH_RULES,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    if not response.text:
        raise RuntimeError(f"Gemini returned no research notes: {response.prompt_feedback or response.candidates}")

    notes = response.text
    # Append the pages Google Search actually returned, so the card's source comes from real results.
    metadata = response.candidates[0].grounding_metadata if response.candidates else None
    chunks = (metadata.grounding_chunks or []) if metadata else []
    sources = [f"- {c.web.title}: {c.web.uri}" for c in chunks if c.web]
    if sources:
        notes += "\n\nSearch results used:\n" + "\n".join(sources)
    return notes


def find_story(cfg: dict, previous: list[str], category: str | None = None) -> tuple[NewsStory, str]:
    client = genai.Client()  # reads GEMINI_API_KEY
    notes = _research(client, cfg, previous, category)

    response = client.models.generate_content(
        model=cfg["gemini"]["text_model"],
        contents=(
            f"Research notes:\n\n{notes}\n\n"
            f"Write the card. Use exactly {cfg['content']['hashtags_count']} hashtags (Gujarati and English mix). "
            "For source_name use the news outlet's name (e.g. 'Divya Bhaskar'), not a search domain."
        ),
        config=types.GenerateContentConfig(
            system_instruction=FORMAT_RULES,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
        ),
    )
    if not response.text:
        raise RuntimeError(f"Gemini returned no card text: {response.prompt_feedback or response.candidates}")
    return NewsStory(**json.loads(response.text)), notes
