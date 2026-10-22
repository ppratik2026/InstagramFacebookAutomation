"""Find a real, recent Gujarat news story with Claude + web search, then turn it into card content."""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import anthropic

IST = timezone(timedelta(hours=5, minutes=30))
MAX_CONTINUATIONS = 5

RESEARCH_SYSTEM = """You are a news researcher for a Gujarati Instagram news page.
Use web search to find ONE real, verifiable news story. Prefer established outlets
(Divya Bhaskar, Sandesh, Gujarat Samachar, TV9 Gujarati, ABP Asmita, News18 Gujarati,
Times of India, Indian Express, DeshGujarat, official gujarat.gov.in / gseb.org pages).

Hard rules:
- Never invent or guess facts, numbers, dates or names. Everything must come from the sources you read.
- Prefer stories confirmed by at least two sources, or by one official source.
- Crime stories: do not name or describe victims of sexual offences or any minor; call unconvicted people
  "accused"; no graphic details; no communal angle.
- Skip rumours, unverified viral claims and anything older than the allowed age."""

FORMAT_SYSTEM = """You turn research notes into the text of one Gujarati Instagram news card.
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
                "additionalProperties": False,
            },
        },
        "cta": {"type": "string", "description": "Bottom line asking viewers to comment/share."},
        "caption": {"type": "string", "description": "Instagram caption in Gujarati, 3-5 short lines summarising the news, no hashtags."},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "image_keywords": {
            "type": "array",
            "items": {"type": "string"},
            "description": "2-3 English stock-photo searches for a generic background (places/objects, never real people).",
        },
        "source_name": {"type": "string"},
        "source_url": {"type": "string"},
    },
    "required": [
        "category", "title_en", "kicker", "headline", "subheadline", "facts", "cta",
        "caption", "hashtags", "image_keywords", "source_name", "source_url",
    ],
    "additionalProperties": False,
}


@dataclass
class NewsStory:
    category: str
    title_en: str
    kicker: str
    headline: str
    subheadline: str
    facts: list[dict]
    cta: str
    caption: str
    hashtags: list[str]
    image_keywords: list[str]
    source_name: str
    source_url: str

    def full_caption(self) -> str:
        tags = " ".join(t if t.startswith("#") else f"#{t}" for t in self.hashtags)
        return f"{self.caption}\n\nસ્રોત: {self.source_name}\n\n{tags}".strip()


def _create(client: anthropic.Anthropic, cfg: dict, **kwargs):
    response = client.beta.messages.create(
        model=cfg["claude"]["model"],
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        **kwargs,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Claude's response was cut off (max_tokens).")
    return response


def _research(client: anthropic.Anthropic, cfg: dict, previous: list[str], category: str | None) -> str:
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

    messages = [{"role": "user", "content": prompt}]
    tools = [{
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": 8,
        "user_location": {"type": "approximate", "country": "IN", "region": "Gujarat", "city": "Ahmedabad", "timezone": "Asia/Kolkata"},
    }]

    for _ in range(MAX_CONTINUATIONS):
        response = _create(
            client, cfg, system=RESEARCH_SYSTEM, messages=messages, tools=tools,
            output_config={"effort": cfg["claude"]["effort"]},
        )
        if response.stop_reason != "pause_turn":
            return "".join(b.text for b in response.content if b.type == "text")
        # long searches pause; send the turn back and the server resumes it
        messages = [messages[0], {"role": "assistant", "content": response.content}]
    raise RuntimeError("News research did not finish.")


def find_story(cfg: dict, previous: list[str], category: str | None = None) -> tuple[NewsStory, str]:
    client = anthropic.Anthropic()
    notes = _research(client, cfg, previous, category)

    response = _create(
        client, cfg,
        system=FORMAT_SYSTEM,
        messages=[{"role": "user", "content": (
            f"Research notes:\n\n{notes}\n\n"
            f"Write the card. Use exactly {cfg['content']['hashtags_count']} hashtags (Gujarati and English mix)."
        )}],
        output_config={"effort": cfg["claude"]["effort"], "format": {"type": "json_schema", "schema": SCHEMA}},
    )
    text = next(b.text for b in response.content if b.type == "text")
    return NewsStory(**json.loads(text)), notes
