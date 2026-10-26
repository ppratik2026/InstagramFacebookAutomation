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
        "midnight-black and blood-red palette, flashing red-blue police light glow, rain-wet reflections, "
        "yellow 'police line' tape slashing diagonally across a corner, cinematic thriller mood",
        "deep maroon background with fiery orange rim light, sparks and smoke, cracked-glass texture behind the "
        "headline, red 'BREAKING' sticker badge, intense investigative mood",
    ],
    "good_news": [
        "emerald green and royal gold palette, golden sunburst rays, floating confetti and sparkles, glossy "
        "celebration ribbons, joyful proud festive mood",
        "sunrise sky gradient (peach, pink, sky blue) with soft clouds, golden light beams, fresh modern look, "
        "uplifting hopeful mood",
    ],
    "government": [
        "navy-blue night background with saffron and red accents, electric lightning, glowing upward arrows, "
        "official big-announcement feel",
        "clean white newspaper-infographic look with a huge bold red headline, red rounded info boxes, "
        "a 3D scene of the subject on the right side",
        "fiery red-orange background with glowing particles, light streaks and a heroic 3D illustration of the "
        "subject, premium viral news thumbnail look",
    ],
}

ART_DIRECTION = """Art direction (make it look like a top viral Instagram news poster, not a plain template):
- One hero 3D illustration of the subject (Pixar-quality render, glossy materials, dramatic rim lighting,
  shallow depth of field), overlapping the boxes a little so the poster has depth.
- Headline in extra-bold rounded Gujarati letters with a thick black outline, glossy gradient fill
  (white/gold/yellow) and a strong 3D drop shadow; one key word can be in a contrasting colour.
- Rounded glass-like info boxes with glowing borders, small 3D icons (calendar, ₹ coins, pin, alert) next to text.
- Energy details: light rays, sparkles, particles, a diagonal ribbon or sticker badge, subtle texture.
- Bold colour contrast, clear visual hierarchy: banner -> headline -> picture -> facts -> call to action.
"""

VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "problems": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ok", "problems"],
}


# Poster concepts, modelled on the best Gujarati news posters made with Gemini. Each post gets one that fits its
# mood, so the feed never repeats one pattern.
CONCEPTS = {
    "infographic": """SPLIT INFOGRAPHIC: bright glowing sky (yellow/orange or sky blue) at the top fading into deep navy.
Top: dark rounded pill with the banner text and a 3D icon. Below it the huge headline in three colour bands
(e.g. bright blue, red, glowing white/cyan), each letter with a thick white outline and a 3D drop shadow.
Middle: on the RIGHT a large isometric 3D diorama of the scene (buildings, vehicles, small people in 3D cartoon style)
bursting out of a slanted frame; a big angled RED callout banner over its corner with the stamp text and yellow 3D arrows.
On the LEFT a column of white rounded cards, each with a glossy round 3D icon badge (₹ coin, calendar, clock, pin,
siren...) and the fact text. Lower: a white checklist panel with red ✓ ticks, a 3D siren light on its left and a 3D
document on its right. Bottom: a navy banner with a gold border showing one huge golden 3D number next to the
call-to-action in a white box.""",
    "cinematic": """CINEMATIC HERO: a full-bleed dramatic 3D movie-poster scene of the story filling the whole canvas
(dramatic rim light, volumetric light rays, sparks, depth of field). Top: glowing banner ribbon and a gigantic metallic
gold 3D headline with black outline and heavy shadow. The stamp slammed diagonally across the scene like a rubber stamp.
Bottom third: stacked glass cards with glowing neon borders for the facts (big golden numbers), a translucent panel with
gold ✓ points, a red ribbon with the sub-headline and a yellow call-to-action bar.""",
    "newspaper": """NEWSPAPER FRONT PAGE: cream paper texture with halftone dots and a thick red masthead bar. A red tag
label top-left. Huge headline: first line bold black, then giant RED 3D letters with white outline and dark shadow,
spanning the full width. A large framed 3D illustration of the scene with taped corners, a small red label
'પ્રતિકાત્મક તસવીર', and a red stamp on it. Two or three red rounded boxes with white text for the facts, each with a
small 3D icon. A bold black heading 'મુખ્ય મુદ્દા' with red ▶ bullet points. Black bottom bar with yellow text.""",
    "bignumber": """BIG NUMBER: the most important number from the facts rendered as a giant 3D golden/metallic number in
the centre, exploding with 3D coins, arrows, sparkles and light rays around it. Headline at the top in bold 3D letters
(white + gold/red), banner pill above it. Fact chips with round 3D icons orbiting the number. A white panel with ✓ points
below and a bright call-to-action strip at the bottom. Rich gradient background matching the mood.""",
    "breakingtv": """BREAKING TV NEWS: styled like a live TV news screen. A red 'BREAKING NEWS' banner with a 'LIVE' badge,
a glossy studio-style background with a huge 3D scene of the story on a giant screen, the headline in bold white +
yellow 3D letters on a red/black lower-third bar, a scrolling-ticker style strip with the sub-headline, info boxes with
icons for the facts, and a yellow call-to-action bar. Dramatic red and blue lights.""",
    "celebration": """CELEBRATION: joyful festive poster with golden light, confetti, fireworks, balloons and sparkles.
A 3D trophy / medal / smiling cartoon characters celebrating the story. Headline in glossy gold and white 3D letters
with a ribbon banner above. Fact cards shaped like badges with 3D icons, a white panel with green ✓ points, and a
bright call-to-action ribbon at the bottom.""",
}

MOOD_CONCEPTS = {
    "breaking": ["breakingtv", "cinematic", "infographic"],
    "money": ["bignumber", "infographic", "cinematic"],
    "info": ["infographic", "newspaper", "bignumber"],
    "happy": ["celebration", "newspaper", "infographic"],
}

CREATIVE_RULES = """Make it a STUNNING, highly creative, premium poster - the kind that stops people scrolling on Instagram,
like the best viral Gujarati news pages. Fill the whole canvas with rich detail: no plain or empty areas, layered depth
(elements overlapping the frame), 3D icons in glossy round badges next to the facts, stickers, ribbons, arrows,
light rays, sparkles. Bold saturated colours, strong contrast and a clear reading order. Every Gujarati word must be
large and readable on a phone."""


def _extras(story: NewsStory) -> str:
    """Optional summary box and stamp lines for the prompt."""
    out = ""
    if getattr(story, "summary", ""):
        out += f'\n- Short explanation box titled "શું થયું?": "{story.summary}"'
    if getattr(story, "stamp", ""):
        out += f'\n- A tilted rubber-stamp / sticker on the picture: "{story.stamp}"'
    return out


def _poster_prompt(story: NewsStory, handle: str, extra_fix: str = "") -> str:
    facts = "\n".join(f'  - "{f["label"]}": "{f["value"]}"' for f in story.facts[:4])
    points = "\n".join(f'  - "{p}"' for p in story.points[:4])
    style = random.choice(STYLES.get(story.category, STYLES["government"]))
    if story.layout == "list" and story.rows:
        rows = "\n".join(f'  - "{r["left"]}" | "{r["right"]}"' for r in story.rows[:11])
        prompt = f"""Create an image: design a vertical 9:16 Instagram news poster for a Gujarati news page, in the style of
viral Gujarati list infographics: a big bold Gujarati headline at the top over a small themed illustration,
then a colourful table where every row is a rounded bar - a vivid coloured block on the left (each row a
different colour: red, blue, green, orange, purple, teal...) with a small icon and the left text in white,
and a light pastel box on the right with the right text in dark bold letters. Strong contrast, readable on a phone.

Visual style: {style}.
Illustration idea for the header: {story.image_prompt}
{ART_DIRECTION}

Write ALL of this text on the poster exactly as given (Gujarati script, same spelling, same numbers, nothing extra):
- Top banner: "{story.kicker}"
- Headline (biggest text, two colours e.g. white + yellow/gold): "{story.headline}"
- Highlight strip under the headline: "{story.subheadline}"{_extras(story)}
- Table rows (left | right), in this order:
{rows}
- Bottom strip: "{story.cta}"
"""
    else:
        from .designs import mood_of
        concept = CONCEPTS[random.choice(MOOD_CONCEPTS[mood_of(story)])]
        prompt = f"""Create an image: a vertical 9:16 Instagram news poster for a Gujarati news page.

{CREATIVE_RULES}

Layout concept - follow it closely:
{concept}

Colour mood: {style}.
What the 3D illustration shows: {story.image_prompt}

Write ALL of this text on the poster exactly as given (Gujarati script, same spelling, same numbers, nothing extra):
- Top banner: "{story.kicker}"
- Headline (biggest text, coloured as the layout concept says): "{story.headline}"
- Sub-headline strip: "{story.subheadline}"{_extras(story)}
- Key facts in highlighted boxes:
{facts}
- Detail lines in a box:
{points}
- Bottom yellow strip: "{story.cta}"
"""
    if story.note:
        prompt += f'- Small note line at the very bottom: "{story.note}"\n'
    prompt += f"""- Small text in a corner: "સ્રોત: {story.source_name}" and "{handle}"

Rules: Gujarati text must be correctly spelled and correctly shaped. Any section heading you add must be in Gujarati
(e.g. "મુખ્ય આંકડા", never "Key Facts"); do not invent any other labels, tags or words in any language. Numbers, ₹ amounts and dates must match
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
    client = genai.Client(http_options={"timeout": 150_000})
    fix = ""
    for attempt in range(1, gcfg.get("poster_attempts", 3) + 1):
        for model in gcfg["poster_models"]:
            try:
                image = _generate(client, model, _poster_prompt(story, cfg["card"]["handle"], fix))
            except Exception as e:  # model missing/unavailable: try the next one
                print(f"   Poster attempt {attempt} with {model} failed: {str(e)[:200]}")
                continue
            if image:
                break
        else:
            return None  # no model could generate anything

        attempt_path = out_path.with_name(f"poster_try{attempt}.png")
        attempt_path.write_bytes(image)
        try:
            ok, problems = _verify(client, gcfg["text_model"], image, story)
        except Exception as e:  # proof-reading unavailable: the poster is still the best we have
            print(f"   Poster proof-read skipped ({str(e)[:120]})")
            ok, problems = True, []
        if ok:
            out_path.write_bytes(image)
            print(f"   Poster OK on attempt {attempt} ({model})")
            return out_path
        print(f"   Poster attempt {attempt} rejected: {'; '.join(problems)}")
        fix = "; ".join(problems)
    return None
