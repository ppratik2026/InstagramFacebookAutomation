"""Full AI-designed news poster (Gemini image model), checked by Gemini before it is used.

The image model draws the whole poster - illustration, layout and Gujarati text - like popular
Gujarati news pages. Image models can still misspell text or change a number, so every poster is
read back and compared with the story; a poster that fails is regenerated, and after the last
attempt the caller falls back to the HTML template card.
"""
import json
import random
from pathlib import Path

from google import genai
from google.genai import types

from .news import NewsStory

STYLES = {
    "crime": [
        "dark red and black dramatic background, police lights glow, sparks, red alert banner at the top",
        "deep maroon background with fiery orange light, breaking-news red ribbons and warning icons",
    ],
    "good_news": [
        "bright green and gold celebratory background, sunrays, confetti, proud and positive mood",
        "fresh teal and white background with golden highlights, clean modern look, happy mood",
    ],
    "government": [
        "navy blue background with orange and red accents, lightning and upward arrows, official announcement feel",
        "clean light background (white/sky blue) with a bold red headline and red information boxes, like a newspaper infographic",
        "dark red-orange background with glowing particles and a 3D illustration of the subject, premium news thumbnail look",
    ],
}

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "problems": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ok", "problems"],
}


def _poster_prompt(story: NewsStory, handle: str, extra_fix: str = "") -> str:
    facts = "\n".join(f'  - "{f["label"]}": "{f["value"]}"' for f in story.facts[:4])
    points = "\n".join(f'  - "{p}"' for p in story.points[:4])
    style = random.choice(STYLES.get(story.category, STYLES["government"]))
    if story.layout == "list" and story.rows:
        rows = "\n".join(f'  - "{r["left"]}" | "{r["right"]}"' for r in story.rows[:11])
        prompt = f"""Design a vertical 9:16 Instagram news poster for a Gujarati news page, in the style of
viral Gujarati list infographics: a big bold Gujarati headline at the top over a small themed illustration,
then a colourful table where every row is a rounded bar - a vivid coloured block on the left (each row a
different colour: red, blue, green, orange, purple, teal...) with a small icon and the left text in white,
and a light pastel box on the right with the right text in dark bold letters. Strong contrast, readable on a phone.

Visual style: {style}.
Illustration idea for the header: {story.image_prompt}

Write ALL of this text on the poster exactly as given (Gujarati script, same spelling, same numbers, nothing extra):
- Top banner: "{story.kicker}"
- Headline (biggest text, two colours e.g. white + yellow/gold): "{story.headline}"
- Highlight strip under the headline: "{story.subheadline}"
- Table rows (left | right), in this order:
{rows}
- Bottom strip: "{story.cta}"
"""
    else:
        prompt = f"""Design a vertical 9:16 Instagram news poster for a Gujarati news page, in the style of
viral Gujarati news infographics: huge bold Gujarati headline, eye-catching 3D illustration of the topic,
rounded information boxes, strong contrast, everything readable on a phone.

Visual style: {style}.
Illustration idea: {story.image_prompt}

Write ALL of this text on the poster exactly as given (Gujarati script, same spelling, same numbers, nothing extra):
- Top banner: "{story.kicker}"
- Headline (biggest text, two colours e.g. white + yellow/gold): "{story.headline}"
- Sub-headline strip: "{story.subheadline}"
- Key facts in highlighted boxes:
{facts}
- Detail lines in a box:
{points}
- Bottom yellow strip: "{story.cta}"
"""
    if story.note:
        prompt += f'- Small note line at the very bottom: "{story.note}"\n'
    prompt += f"""- Small text in a corner: "સ્રોત: {story.source_name}" and "{handle}"

Rules: Gujarati text must be correctly spelled and correctly shaped. Numbers, ₹ amounts and dates must match
exactly. Do not add any other text, logos or watermarks. No real, recognisable people. Keep a margin of about
5% on every side so nothing touches the edges."""
    if extra_fix:
        prompt += f"\n\nThe previous attempt had these mistakes, fix them: {extra_fix}"
    return prompt


def _generate(client: genai.Client, model: str, prompt: str) -> bytes | None:
    image_config = types.ImageConfig(aspect_ratio="9:16")
    if model.startswith("gemini-3"):
        image_config.image_size = "2K"  # sharper text; older image models only make 1K
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=image_config),
    )
    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
    return None


def _verify(client: genai.Client, model: str, image: bytes, story: NewsStory) -> tuple[bool, list[str]]:
    expected = {
        "kicker": story.kicker, "headline": story.headline, "subheadline": story.subheadline,
        "cta": story.cta,
    }
    if story.layout == "list" and story.rows:
        expected["rows"] = story.rows[:11]
    else:
        expected |= {"facts": story.facts[:4], "points": story.points[:4]}
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=image, mime_type="image/png"),
            "Proof-read this Gujarati news poster against the expected text below.\n"
            f"{json.dumps(expected, ensure_ascii=False, indent=2)}\n\n"
            "ok=false if ANY number, ₹ amount, date or name differs, if any expected item is missing, if Gujarati "
            "words are misspelled or garbled (broken letters, wrong matras), or if there is extra made-up text. "
            "Small styling differences and line breaks are fine. List each problem briefly in English.",
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=VERIFY_SCHEMA),
    )
    result = json.loads(response.text)
    return bool(result["ok"]), result.get("problems", [])


def make_poster(story: NewsStory, cfg: dict, out_path: Path) -> Path | None:
    """Return the path of a verified poster, or None if no attempt passed the check."""
    gcfg = cfg["gemini"]
    client = genai.Client()
    fix = ""
    for attempt in range(1, gcfg.get("poster_attempts", 3) + 1):
        for model in gcfg["poster_models"]:
            try:
                image = _generate(client, model, _poster_prompt(story, cfg["card"]["handle"], fix))
            except Exception as e:  # model missing/unavailable: try the next one
                print(f"   Poster attempt {attempt} with {model} failed: {e}")
                continue
            if image:
                break
        else:
            return None  # no model could generate anything

        attempt_path = out_path.with_name(f"poster_try{attempt}.png")
        attempt_path.write_bytes(image)
        ok, problems = _verify(client, gcfg["text_model"], image, story)
        if ok:
            out_path.write_bytes(image)
            print(f"   Poster OK on attempt {attempt} ({model})")
            return out_path
        print(f"   Poster attempt {attempt} rejected: {'; '.join(problems)}")
        fix = "; ".join(problems)
    return None
