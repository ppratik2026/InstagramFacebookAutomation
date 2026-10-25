"""Image for the news card: free AI illustration (Pollinations) or Gemini, then a Pexels photo, else none."""
import os
import random
import re
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


def _keyed_image(prompt: str, out_path: Path, size: str) -> Path | None:
    """One picture from Pollinations' images API with the free account key (POLLINATIONS_API_KEY), or None."""
    key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("POLLINATIONS_IMAGE_MODEL", "gptimage")
    try:
        resp = requests.post(POLLINATIONS_IMAGES_API, headers={"Authorization": f"Bearer {key}"},
                             json={"model": model, "prompt": prompt, "size": size, "n": 1}, timeout=300)
        if resp.status_code != 200:
            print(f"AI image ({model}) failed: HTTP {resp.status_code} {resp.text[:150]!r}")
            return None
        item = resp.json()["data"][0]
        if item.get("b64_json"):
            import base64
            out_path.write_bytes(base64.b64decode(item["b64_json"]))
        else:
            with requests.get(item["url"], timeout=120) as dl:
                dl.raise_for_status()
                out_path.write_bytes(dl.content)
        return out_path
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print(f"AI image ({model}) failed: {e}")
        return None


def generate_free_ai_image(prompt: str, out_path: Path) -> Path | None:
    """Free AI illustration from Pollinations (no key). None if it fails; never stops the run."""
    # stylised 3D characters keep it clearly illustrative: never a real, recognisable person
    full = (f"{prompt}, Pixar style 3D render, cinematic news thumbnail, vivid colours, dramatic rim lighting, "
            "shallow depth of field, anonymous characters, no real person. "
            "IMPORTANT: absolutely no text anywhere in the image - no letters, numbers, words, signs, sign boards, "
            "banners, posters, labels, logos, stamps, price tags or watermarks; any board or screen must be blank")
    if _keyed_image(full, out_path, "1024x1536"):   # with the free account key: a better model than keyless
        print("Background: AI illustration (Pollinations key)")
        return out_path
    url = POLLINATIONS_IMAGE + urllib.parse.quote(full)
    # a bit taller than 9:16: the cards show the top of the image, so the watermark strip at the bottom is cut off
    params = {"width": 1080, "height": 2040, "nologo": "true", "seed": random.randint(1, 10**6)}
    for attempt in range(4):
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
        if resp.status_code not in (402, 429, 500, 502, 503, 504) or attempt == 3:
            return None
        # busy or rate limited (anonymous use is limited per IP): wait as asked, then retry
        match = re.search(r"[Rr]etry after (\d+)", resp.text)
        time.sleep(min(int(match.group(1)) + 5 if match else 20, 60))
    return None


POLLINATIONS_IMAGES_API = "https://gen.pollinations.ai/v1/images/generations"


def fit_to_reel(path: Path) -> Path:
    """Make a poster 1080x1920 without cutting it: the whole poster in the middle on a blurred copy of itself."""
    from PIL import Image, ImageFilter

    img = Image.open(path).convert("RGB")
    if abs(img.width / img.height - 9 / 16) < 0.01:
        return path
    back = img.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(40))
    scale = min(1080 / img.width, 1920 / img.height)
    front = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    back.paste(front, ((1080 - front.width) // 2, (1920 - front.height) // 2))
    back.save(path)
    return path


def generate_free_poster(prompt: str, models: list[str], out_path: Path) -> Path | None:
    """The whole poster (picture + Gujarati text) from the same prompt a person would paste into Gemini.
    Needs a free Pollinations account key (POLLINATIONS_API_KEY): the keyless API only has a model that
    cannot write text. Returns None if there is no key or no model gives an image."""
    key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if not key:
        print("   AI poster skipped: no POLLINATIONS_API_KEY (free key from enter.pollinations.ai).")
        return None
    for model in models:
        for attempt in range(2):
            try:
                resp = requests.post(POLLINATIONS_IMAGES_API, headers={"Authorization": f"Bearer {key}"},
                                     json={"model": model, "prompt": prompt, "size": "1024x1536", "n": 1},
                                     timeout=300)
            except requests.RequestException as e:
                print(f"   AI poster ({model}) failed: {e}")
                break
            if resp.status_code == 200:
                try:
                    item = resp.json()["data"][0]
                    if item.get("b64_json"):
                        import base64
                        out_path.write_bytes(base64.b64decode(item["b64_json"]))
                    else:
                        with requests.get(item["url"], timeout=120) as dl:
                            dl.raise_for_status()
                            out_path.write_bytes(dl.content)
                except (ValueError, KeyError, IndexError, requests.RequestException) as e:
                    print(f"   AI poster ({model}) gave no image: {e}")
                    break
                print(f"   AI poster made with model '{model}'")
                return fit_to_reel(out_path)
            print(f"   AI poster ({model}) failed: HTTP {resp.status_code} {resp.text[:200]!r}")
            if resp.status_code not in (429, 500, 502, 503, 504):
                break   # e.g. out of free credits or model unavailable: try the next model
            time.sleep(20)
    return None


def remove_white_background(path: Path, out_path: Path) -> Path | None:
    """Make the plain light background of an object picture transparent (flood fill from the edges, so white
    parts inside the object stay). Returns None if the picture has no plain background to remove."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    img = Image.open(path).convert("RGB")
    img.thumbnail((1200, 1200))
    key = (255, 0, 255)
    filled = img.copy()
    w, h = filled.size
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        if sum(filled.getpixel(xy)) > 600:          # only light corners/edges are background
            ImageDraw.floodfill(filled, xy, key, thresh=38)
    diff = ImageChops.difference(filled, Image.new("RGB", filled.size, key)).convert("L")
    mask = diff.point(lambda v: 255 if v > 8 else 0).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    box = mask.getbbox()
    if not box:
        return None
    kept = sum(1 for v in mask.getdata() if v > 128) / (w * h)
    if not 0.05 < kept < 0.92:                      # nothing removed, or the object was eaten: not usable
        print(f"   Cut-out not usable ({kept:.0%} of the picture kept)")
        return None
    out = img.convert("RGBA")
    out.putalpha(mask)
    out.crop(box).save(out_path)
    return out_path


def generate_cutout(object_prompt: str, out_path: Path) -> Path | None:
    """The story's main objects as a transparent 3D sticker (needs POLLINATIONS_API_KEY for a good model)."""
    if not object_prompt or not os.environ.get("POLLINATIONS_API_KEY", "").strip():
        return None
    prompt = (f"{object_prompt}. Glossy 3D render like a premium news infographic sticker, vivid colours, soft studio "
              "lighting, the objects grouped together in the centre, filling most of the frame, isolated on a plain "
              "pure white background, no floor, no shadow on the background, nothing else in the picture. "
              "IMPORTANT: absolutely no text, letters, numbers, labels, logos or currency symbols anywhere.")
    raw = out_path.with_name("cutout_raw.png")
    if not _keyed_image(prompt, raw, "1024x1024"):
        return None
    path = remove_white_background(raw, out_path)
    if path:
        print("Cut-out: 3D object sticker made")
    return path


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
