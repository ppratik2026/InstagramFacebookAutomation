import os
import random
from pathlib import Path

import requests

PEXELS_PHOTOS = "https://api.pexels.com/v1/search"


def fetch_background(keywords: list[str], out_path: Path) -> Path | None:
    """Download a portrait stock photo from Pexels for the card background. None if unavailable."""
    api_key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not api_key:
        print("PEXELS_API_KEY not set, using a plain background.")
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
        print(f"Background photo for {keyword!r} by {photo.get('photographer')} (Pexels)")
        return out_path
    return None
