"""The page's one brand template: the same layout on every post, only the category colour changes, so the
profile grid looks like one page.

Fixed zones on the 1080x1920 reel (the profile grid shows only the middle 1080x1440, from y=240 to 1680):
  0-230     brand bar: category and date (cut off in the grid)
  236-588   headline, its key word highlighted
  596-742   "what happened" summary
  750-1270  the story's 3D cut-out (or a big 3D icon) on a glow, with the key number as a badge
  1278-1670 always three rows of the same height: icon, label, value
  1700-1920 follow line, source and handle (Instagram's buttons cover this part)
Every text box keeps its size; long text only gets a smaller font.
"""
import re

from src.designs import esc, highlight_numbers
from src.icons import available, icon_img, icon_key

# category -> (label, icon, background top, background bottom, accent, value colour on the white rows)
LOOKS = {
    "government": ("સરકારી જાહેરાત", "govt", "#0d3a8c", "#061a42", "#ffc93c", "#0d3a8c"),
    "politics": ("રાજકારણ", "vote", "#4a1676", "#1b0630", "#ffb347", "#4a1676"),
    "crime": ("ક્રાઇમ", "police", "#5c0b0b", "#120404", "#ff4d4d", "#b3001b"),
    "trending": ("ટ્રેન્ડિંગ", "fire", "#8a3300", "#2b1000", "#ffd23f", "#c2410c"),
    "good_news": ("સારા સમાચાર", "trophy", "#0d5c34", "#03231a", "#ffe14d", "#0d6b3a"),
}

FONT = "Baloo Bhai 2"
BODY_FONT = "Hind Vadodara"

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1080px; height: 1920px; overflow: hidden; }
body { font-family: '%(body)s', 'Noto Sans Gujarati', sans-serif; color: #fff; position: relative;
  background: radial-gradient(ellipse at 50%% 55%%, %(top)s 0%%, %(bottom)s 75%%); }
body::before { content: ""; position: absolute; inset: 0; opacity: .07;
  background: repeating-linear-gradient(135deg, #fff 0 2px, transparent 2px 46px); }
.zone { position: absolute; left: 44px; right: 44px; }
[data-fit] { overflow: hidden; }

.bar { top: 60px; height: 130px; display: flex; align-items: center; justify-content: space-between; }
.chip { display: flex; align-items: center; gap: 14px; background: %(accent)s; color: #111; border-radius: 60px;
  padding: 10px 34px 10px 14px; font: 800 44px/1.1 '%(font)s', sans-serif; }
.chip .ic { width: 70px; height: 70px; }
.date { font: 700 36px/1.2 '%(body)s', sans-serif; opacity: .9; text-align: right; }

.hl { top: 236px; height: 352px; display: flex; align-items: center; justify-content: center; text-align: center;
  font-family: '%(font)s', sans-serif; font-weight: 800; line-height: 1.12; text-wrap: balance;
  text-shadow: 0 6px 0 rgba(0,0,0,.35), 0 0 40px rgba(0,0,0,.4); }
.hl .hi { color: %(accent)s; }

.sum { top: 596px; height: 146px; background: rgba(255,255,255,.12); border: 2px solid rgba(255,255,255,.25);
  border-radius: 26px; padding: 14px 26px; display: flex; align-items: center; font-weight: 600; line-height: 1.32; }
.sum b { color: %(accent)s; margin-right: 8px; font-weight: 800; }
.sum .num { color: %(accent)s; font-weight: 800; }

.hero { top: 750px; height: 520px; display: flex; align-items: center; justify-content: center; }
.glow { position: absolute; width: 560px; height: 560px; border-radius: 50%%;
  background: radial-gradient(circle, rgba(255,255,255,.55) 0%%, %(accent)s55 35%%, transparent 70%%); }
.hero .obj { position: relative; max-width: 78%%; max-height: 100%%; object-fit: contain;
  filter: drop-shadow(0 30px 30px rgba(0,0,0,.55)); }
/* the scene has no frame: it spans the full width and fades into the background at every edge */
.hero.has-scene { left: 0; right: 0; top: 700px; height: 640px; z-index: 0; }
.hero .scene { position: absolute; inset: 0; background: center/cover no-repeat;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%%, #000 22%%, #000 72%%, transparent 100%%),
                      linear-gradient(to right, transparent 0%%, #000 9%%, #000 91%%, transparent 100%%);
  -webkit-mask-composite: source-in; mask-composite: intersect; }
.hero.has-scene .badge { left: 44px; bottom: 96px; z-index: 2; }
.sum, .rows, .hl { z-index: 1; }
.hero .icon-big { position: relative; width: 420px; height: 420px; filter: drop-shadow(0 30px 30px rgba(0,0,0,.5)); }
.badge { position: absolute; left: 0; bottom: 18px; max-width: 470px; background: %(accent)s; color: #111;
  border-radius: 24px; padding: 12px 28px 16px; transform: rotate(-4deg); box-shadow: 0 16px 30px rgba(0,0,0,.45);
  text-align: center; }
.badge small { display: block; font: 700 32px/1.15 '%(body)s', sans-serif; }
.badge b { display: block; font: 800 84px/1 '%(font)s', sans-serif; white-space: nowrap; }

.rows { top: 1278px; height: 392px; display: flex; flex-direction: column; overflow: hidden; }
.row { flex: 1 1 0; min-height: 0; overflow: hidden; margin: 7px 0; display: flex; align-items: center; gap: 18px; background: #fff; color: #161616;
  border-radius: 24px; padding: 0 22px 0 14px; box-shadow: 0 10px 22px rgba(0,0,0,.3); }
.row .ic { width: 84px; height: 84px; flex-shrink: 0; }
.row .txt { flex: 1; height: 100%%; padding: 8px 0; display: flex; flex-direction: column; justify-content: center; line-height: 1.2; }
.row small { display: block; color: #666; font-weight: 700; }
.row strong { display: block; color: %(value)s; font-weight: 800; }

.foot { top: 1700px; height: 190px; display: flex; flex-direction: column; align-items: center; gap: 14px; }
.cta { background: %(accent)s; color: #111; border-radius: 50px; padding: 10px 40px; font: 800 40px/1.2 '%(font)s', sans-serif; }
.src { font: 600 28px/1.2 '%(body)s', sans-serif; opacity: .85; }
"""

# Each [data-fit] box keeps its size: its font starts at data-max and shrinks until the text fits.
FIT = """() => {
  let ok = true;
  for (const el of document.querySelectorAll('[data-fit]')) {
    let size = +el.dataset.max;
    const min = +el.dataset.min;
    const over = () => el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2;
    el.style.fontSize = size + 'px';
    while (over() && size > min) { size -= 2; el.style.fontSize = size + 'px'; }
    if (over()) ok = false;
  }
  return ok;
}"""


def _headline(story) -> str:
    text = esc(story.headline)
    key = story.highlight if story.highlight and story.highlight in story.headline else ""
    if not key:   # else the first number in the headline
        match = re.search(r"₹?\s?[\d૦-૯][\d૦-૯,.]*\s?(%|કરોડ|લાખ)?", story.headline)
        key = match.group(0).strip() if match else ""
    return text.replace(esc(key), f'<span class="hi">{esc(key)}</span>', 1) if key else text


def _badge(story) -> str:
    """The most striking short number of the story (from the facts), e.g. ₹110 કરોડ, 35%, 8 મેડલ."""
    for fact in story.facts:
        if re.search(r"[\d૦-૯]", fact["value"]) and len(fact["value"]) <= 11:
            return f'<div class="badge"><small>{esc(fact["label"])}</small><b>{esc(fact["value"])}</b></div>'
    return ""


def _rows(story) -> list[tuple[str, str, str]]:
    """Exactly three (icon, label, value) rows, from the story's layout data, facts and points."""
    rows: list[tuple[str, str, str]] = []
    c = story.compare or {}
    if story.visual == "compare" and c.get("before") and c.get("after"):
        down = c.get("direction") == "down"
        rows += [("calendar", "પહેલાં", c["before"]), ("chart_down" if down else "chart_up", "હવે", c["after"])]
        if c.get("change"):
            rows.append(("coin", "ફેરફાર", c["change"]))
    elif story.visual in ("table", "timeline"):
        rows += [(r["left"] + " " + r["right"], r["left"], r["right"]) for r in story.rows]
    elif story.visual == "reasons":
        rows += [(r.get("icon") or r["text"], "", r["text"]) for r in story.reasons]
    badge_value = re.search(r"<b>(.*?)</b>", _badge(story))
    for fact in story.facts:   # facts not already in the badge
        if badge_value and esc(fact["value"]) == badge_value.group(1):
            continue
        rows.append((fact["label"] + " " + fact["value"], fact["label"], fact["value"]))
    rows += [(p, "", p) for p in story.points]
    for fact in story.facts:   # still short of three: the badge's fact too, then the subheadline
        rows.append((fact["label"] + " " + fact["value"], fact["label"], fact["value"]))
    if story.subheadline:
        rows.append((story.subheadline, "", story.subheadline))
    seen, unique = set(), []
    for row in rows:
        if row[2] not in seen:
            seen.add(row[2])
            unique.append(row)
    return unique[:3]


def brand_page(story, date: str, handle: str, cutout_url: str | None = None, scene_url: str | None = None) -> str:
    """scene_url: a landscape cartoon scene for the picture zone; else the cut-out, else a big 3D icon."""
    label, icon, top, bottom, accent, value = LOOKS.get(story.category, LOOKS["government"])
    css = CSS % {"font": FONT, "body": BODY_FONT, "top": top, "bottom": bottom, "accent": accent, "value": value}
    story.style.update({"palette": story.category, "visual": story.visual or "checklist"})
    summary = story.summary or story.subheadline
    if scene_url:
        picture = f'<div class="scene" style="background-image:url({scene_url})"></div>'
    elif cutout_url:
        picture = f'<div class="glow"></div><img class="obj" src="{cutout_url}" alt="">'
    else:
        picture = f'<div class="glow"></div>{icon_img(story.headline, "icon-big")}'
    rows = "".join(
        f'<div class="row">{icon_img(key if key in available() else icon_key(key, "check"))}<div class="txt" data-fit data-max="54" data-min="26">'
        f'{f"<small>{esc(lab)}</small>" if lab else ""}<strong>{esc(val)}</strong></div></div>'
        for key, lab, val in _rows(story))
    fonts = f"{FONT.replace(' ', '+')}:wght@600;700;800&family={BODY_FONT.replace(' ', '+')}:wght@600;700"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family={fonts}&display=block" rel="stylesheet">
<style>{css}</style></head><body>
  <div class="zone bar"><div class="chip">{icon_img(icon)}{esc(label)}</div><div class="date">{date}</div></div>
  <div class="zone hl" data-fit data-max="124" data-min="64"><div>{_headline(story)}</div></div>
  {f'<div class="zone sum" data-fit data-max="40" data-min="26"><div><b>શું થયું?</b>{highlight_numbers(summary)}</div></div>' if summary else ''}
  <div class="zone hero{' has-scene' if scene_url else ''}">{picture}{_badge(story)}</div>
  <div class="zone rows">{rows}</div>
  <div class="zone foot"><div class="cta">👉 આવા સમાચાર માટે ફોલો કરો {esc(handle)}</div>
    <div class="src">સ્રોત: {esc(story.source_name)}</div></div>
</body></html>"""
