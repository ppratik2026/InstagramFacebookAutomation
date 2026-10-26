"""Look at the finished poster before it is posted (Gemini reads the image, free tier): cut or overlapping
text, broken letters, empty areas, stickers or stamps that do not fit the news, a picture that does not
match. A poster that scores low is made again in another design."""
import json
import os
import time
from pathlib import Path

MODELS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "1-10: how good and clear this poster is for an Instagram news reel"},
        "problems": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "problems"],
}


def review(card: Path, story) -> tuple[int, list[str]] | None:
    """(score 1-10, problems) for the poster, or None when no image-reading AI is available."""
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    from google import genai
    from google.genai import types

    prompt = f"""You check a Gujarati Instagram news poster (a phone-screen reel) before it is posted.
The news: {story.title_en}. Headline on it: {story.headline}

Check it like a strict designer and editor, and list every problem briefly in English:
- any text cut off, running outside its box or the screen, or overlapping other text or a picture
- broken or garbled Gujarati letters, or English words where Gujarati is expected (names and acronyms are fine)
- big empty areas, cramped or tiny unreadable text, colours that make text hard to read
- stamps, stickers, banners or labels that do not fit this news, or that cover important text
- a picture that has nothing to do with the news, or that could mislead (e.g. a random face for a named person)
Then give a score from 1 (do not post) to 10 (excellent, ready to post)."""
    client = genai.Client(http_options={"timeout": 150_000})
    for model in MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[types.Part.from_bytes(data=card.read_bytes(), mime_type="image/png"), prompt],
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=SCHEMA),
                )
                result = json.loads(response.text)
                return int(result["score"]), [str(p) for p in result.get("problems", [])]
            except Exception as e:   # busy (503) or unavailable: retry once, then the next model
                print(f"   Poster check with {model} failed: {str(e)[:120]}")
                if "503" in str(e) and attempt == 0:
                    time.sleep(8)
                    continue
                break
    return None
