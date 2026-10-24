"""Image for the news card: free AI illustration (Pollinations) or Gemini, then a Pexels photo, else none."""
import os
import random
import time
import urllib.parse
from pathlib import Path

import requests
from google import genai
from google.genai import types

PEXELS_PHOTOS = "https://api.pexels.com/v1/search"


def generate_ai_background(prompt: str, model: str, out_path: Path) -> Path | None:
    """Create a 9:16 illustration with a Gemini image model. Returns None if nothing was generated."""
    try:
        response = genai.Client().models.generate_content(
            model=model,
            contents=(
                f"{prompt}\n\nVertical 9:16 background for a Gujarati news reel. Bold colours, cinematic lighting, "
                "keep the top quarter and bottom third simpler so text can sit on top. "
                "Absolutely no text, letters, numbers, watermarks or logos."
            ),
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="9:16"),
            ),
        )
    except Exception as e:  # image generation is a nice-to-have, never fail the run for it
        print(f"AI background failed: {e}")
        return None

    for candidate in response.candidates or []:
        for part in (candidate.content.parts if candidate.content else None) or []:
            if part.inline_data and part.inline_data.data:
                out_path.write_bytes(part.inline_data.data)
                print("Background: AI illustration (Gemini)")
                return out_path
    print("AI background: no image returned.")
    return None


def fetch_stock_background(keywords: list[str], out_path: Path) -> Path | None:
    """Download a portrait stock photo from Pexels. None if no API key or no result."""
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not api_key:
        return None

    for keyword in keywords:
        resp = requests.get(
            PEXELS_PHOTOS,
            headers={"Authorization": api_key},
            params={"query": keyword, "orientation": "portrait", "per_page": 15},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"Pexels search failed for {keyword!r}: {resp.status_code}")
            continue
        photos = resp.json().get("photos", [])
        if not photos:
            continue
        photo = random.choice(photos[:8])
        with requests.get(photo["src"]["portrait"], timeout=60) as dl:
            dl.raise_for_status()
            out_path.write_bytes(dl.content)
        print(f"Background: Pexels photo for {keyword!r} by {photo.get('photographer')}")
        return out_path
    return None


POLLINATIONS_IMAGE = "https://image.pollinations.ai/prompt/"


def generate_free_ai_image(prompt: str, out_path: Path) -> Path | None:
    """Free AI illustration from Pollinations (no key). None if it fails; never stops the run."""
    full = (f"{prompt}, cinematic news thumbnail illustration, vivid colours, dramatic lighting, "
            "highly detailed 3D render, no text, no letters, no watermark")
    url = POLLINATIONS_IMAGE + urllib.parse.quote(full)
    params = {"width": 1024, "height": 1280, "nologo": "true", "seed": random.randint(1, 10**6)}
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, timeout=120)
        except requests.RequestException as e:
            print(f"Free AI image failed: {e}")
            return None
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
            out_path.write_bytes(resp.content)
            print("Background: free AI illustration (Pollinations)")
            return out_path
        print(f"Free AI image failed: HTTP {resp.status_code} {resp.text[:150]!r}")
        if resp.status_code in (402, 429) and attempt == 0:
            time.sleep(20)  # anonymous use is rate limited per IP
            continue
        return None
    return None


def get_background(story, cfg: dict, work_dir: Path) -> Path | None:
    if cfg.get("provider") != "gemini" and cfg["free"].get("ai_images", True) and story.image_prompt:
        path = generate_free_ai_image(story.image_prompt, work_dir / "illustration.jpg")
        if path:
            return path
    if cfg.get("provider") == "gemini" and cfg["gemini"].get("ai_background", True):
        path = generate_ai_background(story.image_prompt, cfg["gemini"]["image_model"], work_dir / "background.png")
        if path:
            return path
    try:
        path = fetch_stock_background(story.image_keywords, work_dir / "background.jpg")
    except requests.RequestException as e:  # Pexels is optional, never fail the run for it
        print(f"Pexels failed: {e}")
        path = None
    if not path:
        print("Background: theme colours only.")
    return path
