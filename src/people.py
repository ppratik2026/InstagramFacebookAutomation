"""Real photos of well-known people from Wikipedia / Wikimedia Commons (free licences, credited on the card).

Used when a story is about a public figure (a minister, a cricketer, an actor): showing an AI-made face of
someone else would mislead viewers, and photos from news sites are copyrighted. The photo is only used when
the Wikipedia page belongs to a human (checked on Wikidata) and the file has a free licence.
"""
import html
import re
import time
from pathlib import Path

import requests

# Wikimedia asks for a descriptive User-Agent with a contact link (requests without one get throttled)
HEADERS = {"User-Agent": "GujaratNewsReels/1.0 (https://github.com/ppratik2026/InstagramFacebookAutomation)"}
WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# free licences that allow reuse with credit; GODL-India covers most photos of Indian officials and players
FREE = re.compile(r"^(cc0|cc[ -]by|public domain|pd|gfdl|attribution|godl)", re.I)


def _get(url: str, **params) -> dict:
    for attempt in range(3):
        resp = requests.get(url, params={**params, "format": "json"}, headers=HEADERS, timeout=30)
        if resp.status_code != 429 or attempt == 2:
            break
        time.sleep(int(resp.headers.get("retry-after", "5")) + 1)   # throttled: wait as asked
    resp.raise_for_status()
    return resp.json()


def _is_human(qid: str) -> bool:
    data = requests.get(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", headers=HEADERS, timeout=30).json()
    claims = data["entities"][qid]["claims"].get("P31", [])
    return any(c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") == "Q5" for c in claims)


def _plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def person_photo(name: str, out_path: Path) -> tuple[Path, str] | None:
    """(photo, credit line) for a well-known person, or None if there is no usable free photo."""
    if not name:
        return None
    try:
        pages = _get(WIKI_API, action="query", titles=name, prop="pageimages|pageprops", piprop="original|name",
                     redirects=1)["query"]["pages"]
        page = next(iter(pages.values()))
        qid = page.get("pageprops", {}).get("wikibase_item")
        file_name = page.get("pageimage")
        if not (qid and file_name and "original" in page) or "disambiguation" in page.get("pageprops", {}):
            print(f"   No Wikipedia photo for {name!r}")
            return None
        if not _is_human(qid):
            print(f"   {name!r} on Wikipedia is not a person; no photo used")
            return None
        info = next(iter(_get(COMMONS_API, action="query", titles=f"File:{file_name}", prop="imageinfo",
                              iiprop="extmetadata|url", iiurlwidth=1200)["query"]["pages"].values()))
        meta = info["imageinfo"][0]["extmetadata"]
        licence = _plain(meta.get("LicenseShortName", {}).get("value", ""))
        if not FREE.match(licence):
            print(f"   Wikipedia photo of {name!r} has licence {licence!r}; not used")
            return None
        url = info["imageinfo"][0].get("thumburl") or page["original"]["source"]
        img = requests.get(url, headers=HEADERS, timeout=60)
        img.raise_for_status()
        out_path.write_bytes(img.content)
        artist = _plain(meta.get("Artist", {}).get("value", ""))[:40]
        credit = f"ફોટો: {artist + ', ' if artist else ''}Wikimedia Commons ({licence})"
        print(f"   Photo of {page.get('title', name)} from Wikimedia Commons ({licence})")
        return out_path, credit
    except (requests.RequestException, ValueError, KeyError, StopIteration) as e:
        print(f"   Wikipedia photo for {name!r} failed: {e}")
        return None
