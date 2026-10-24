"""Semi-automatic flow through GitHub Issues: the tool prepares the story and a Gemini prompt, a person makes the
poster in the free Gemini app and uploads it as an issue comment, and the tool turns it into a reel and posts it.
"""
import re
from pathlib import Path

import requests

CAPTION_START, CAPTION_END = "<!-- caption-start -->", "<!-- caption-end -->"
TITLE_START, TITLE_END = "<!-- title-start -->", "<!-- title-end -->"


def issue_body(story, prompt: str, caption: str, mood: str = "") -> str:
    """Issue text with the Gemini prompt to copy and the caption the reel will be posted with."""
    return f"""## 📰 {story.headline}

**સ્રોત:** {story.source_name} — {story.source_url}

### 1️⃣ નીચેનો prompt copy કરો
(બોક્સના ખૂણે copy બટન છે)

```text
{prompt}
```

### 2️⃣ Gemini app માં paste કરો → poster બનાવો → image download કરો

### 3️⃣ એ image આ issue માં **comment** તરીકે upload કરો
Reel આપોઆપ બનીને Instagram પર post થઈ જશે, અને અહીં link આવશે ✅

<details><summary>Instagram caption (જરૂર હોય તો અહીં edit કરો)</summary>

{CAPTION_START}
{caption}
{CAPTION_END}

</details>

{TITLE_START}{story.title_en}{TITLE_END}
<!-- mood:{mood} points:{len(story.points)} -->
"""


def _between(text: str, start: str, end: str) -> str:
    match = re.search(re.escape(start) + r"(.*?)" + re.escape(end), text or "", re.S)
    return match.group(1).strip() if match else ""


def caption_from(body: str) -> str:
    return _between(body, CAPTION_START, CAPTION_END)


def title_from(body: str) -> str:
    return _between(body, TITLE_START, TITLE_END)


def style_from(body: str) -> tuple[str, int]:
    """Mood and number of points stored in the issue (decide the reel's motion and length)."""
    match = re.search(r"<!-- mood:(\w*) points:(\d+) -->", body or "")
    return (match.group(1), int(match.group(2))) if match else ("", 0)


def image_url_from(comment: str) -> str | None:
    """First image in a comment: markdown ![..](url) or an <img src="url"> tag (GitHub's upload format)."""
    match = re.search(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", comment or "") or \
        re.search(r"<img[^>]+src=\"(https?://[^\"]+)\"", comment or "")
    return match.group(1) if match else None


def download(url: str, out: Path, token: str) -> Path:
    """Download an issue attachment (needs the token for private repositories)."""
    headers = {"Authorization": f"Bearer {token}"} if token and "github" in url else {}
    resp = requests.get(url, headers=headers, timeout=120, allow_redirects=True)
    resp.raise_for_status()
    if not resp.headers.get("content-type", "").startswith("image/"):
        raise RuntimeError(f"The comment's attachment is not an image ({resp.headers.get('content-type')}).")
    out.write_bytes(resp.content)
    return out
