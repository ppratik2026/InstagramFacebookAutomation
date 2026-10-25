"""Bulletin design, modelled on Gemini-made Gujarati news posters: a two-colour slanted label on top, the
headline on painted strips, a big-number card and an icon card, a checklist next to the AI picture, and a
painted call-to-action strip at the bottom. The picture comes from the image AI (no text in it); every
Gujarati word is real text in a real font, so it is always spelled right.
"""
import random
import re

from src.designs import BRUSH_MASK, FIT_SCRIPT, esc, highlight_numbers
from src.icons import icon_img

# 1) shrink the headline alone until every strip fits on one line, 2) then the generic fit for the rest
FIT = """() => {
  const root = document.documentElement.style;
  let hl = 140;
  const wide = () => [...document.querySelectorAll('.hl div')].some(el => el.scrollWidth > el.clientWidth + 2);
  root.setProperty('--hl', hl + 'px');
  while (wide() && hl > 56) { hl -= 2; root.setProperty('--hl', hl + 'px'); }
  return (""" + FIT_SCRIPT.replace("const v = {hl: 140,", "const v = {hl: parseInt(getComputedStyle(document.documentElement).getPropertyValue('--hl')),") + """)();
}"""


# label colours, page background, strip / card colours and text colours, per look
PALETTES = {
    "maroon": {"bg": "#f7f2ea", "bg2": "#efe4d3", "strip": "#7a0f14", "strip2": "#5c0a0e", "hl": "#ffffff",
               "hl2": "#ffd23f", "card": "#fff3c4", "card_text": "#5c0a0e", "big": "#a4161a", "panel": "#ffffff",
               "panel_head": "#7a0f14", "text": "#1d1d1d", "lines": "rgba(164,22,26,.18)", "gold": "#f5b700", "fg": "#5c0a0e"},
    "navy": {"bg": "#0b1d4d", "bg2": "#061233", "strip": "#c1121f", "strip2": "#8d0b14", "hl": "#ffffff",
             "hl2": "#ffd60a", "card": "#ffd60a", "card_text": "#0b1d4d", "big": "#c1121f", "panel": "#ffffff",
             "panel_head": "#0b1d4d", "text": "#10183a", "lines": "rgba(255,214,10,.14)", "gold": "#ffd60a", "fg": "#ffd60a"},
    "red": {"bg": "#1a0505", "bg2": "#000000", "strip": "#d00000", "strip2": "#9d0208", "hl": "#ffffff",
            "hl2": "#ffea00", "card": "#ffea00", "card_text": "#1a0505", "big": "#d00000", "panel": "#fffaf0",
            "panel_head": "#9d0208", "text": "#1a0505", "lines": "rgba(255,0,0,.16)", "gold": "#ffea00", "fg": "#ffea00"},
    "green": {"bg": "#f1fbef", "bg2": "#dcf3d6", "strip": "#146c2e", "strip2": "#0b4f20", "hl": "#ffffff",
              "hl2": "#ffe14d", "card": "#fff3b0", "card_text": "#0b4f20", "big": "#d9480f", "panel": "#ffffff",
              "panel_head": "#146c2e", "text": "#132a13", "lines": "rgba(20,108,46,.16)", "gold": "#f59e0b", "fg": "#0b4f20"},
}

# (top label, second label) and palettes per mood
MOOD_LOOK = {
    "breaking": (["BREAKING", "NEWS"], ["red", "navy"]),
    "money": (["મહત્વના", "સમાચાર"], ["navy", "maroon"]),
    "info": (["મહત્વના", "સમાચાર"], ["maroon", "navy"]),
    "happy": (["ખુશ", "ખબર"], ["green", "maroon"]),
}

CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: 1920px; overflow: hidden; }
  body { font-family: '%(font)s', 'Noto Sans Gujarati', 'Noto Color Emoji', sans-serif; position: relative;
    color: %(text)s; background:
      repeating-linear-gradient(135deg, transparent 0 46px, %(lines)s 46px 52px, transparent 52px 120px),
      radial-gradient(circle at 50%% 35%%, %(bg)s 0%%, %(bg2)s 100%%); }
  .corner { position: absolute; width: 520px; height: 70px; background: %(strip)s; transform: rotate(-38deg);
    box-shadow: 0 0 0 10px %(gold)s; opacity: .95; }
  #main { position: absolute; inset: 40px 34px 30px; display: flex; flex-direction: column; gap: 20px; z-index: 2; }
  #main > * { flex-shrink: 0; }
  #main > .lower { flex-shrink: 1; }
  .label { display: flex; flex-direction: column; align-items: center; transform: skew(-8deg); }
  .label span { font-weight: 800; font-size: 78px; line-height: 1.08; padding: 0 34px; color: #fff;
    background: %(strip)s; border: 5px solid #fff; box-shadow: 8px 8px 0 rgba(0,0,0,.35); }
  .label span + span { background: %(gold)s; color: #1a1a1a; margin-top: -6px; margin-left: 120px; }
  .hl { display: flex; flex-direction: column; align-items: center; gap: 10px; }
  .hl div { -webkit-mask-image: %(mask)s; -webkit-mask-size: 100%% 100%%; mask-image: %(mask)s; mask-size: 100%% 100%%;
    background: linear-gradient(180deg, %(strip)s, %(strip2)s); color: %(hl)s; font-size: var(--hl); font-weight: 800;
    line-height: 1.22; padding: 8px 46px 14px; text-align: center; text-shadow: 0 5px 0 rgba(0,0,0,.45);
    max-width: 100%%; white-space: nowrap; overflow: hidden; }
  .hl div:nth-child(even) { color: %(hl2)s; }
  /* the one word / number that matters most, extra big in 3D */
  .hl .hi { font-size: 1.32em; color: %(hl2)s; display: inline-block; line-height: 1;
    text-shadow: 0 4px 0 %(strip2)s, 0 8px 0 rgba(0,0,0,.45), 0 0 30px rgba(255,220,80,.35); }
  .hl div:nth-child(even) .hi { color: #fff; }
  .sub { text-align: center; font-size: var(--sub); font-weight: 800; color: %(fg)s; line-height: 1.25; }
  .cards { display: grid; grid-template-columns: 1.15fr 1fr; gap: 22px; }
  .card { border-radius: 30px; padding: 18px 24px; display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center; box-shadow: 0 14px 30px rgba(0,0,0,.28); border: 5px solid #fff; }
  .card.big { background: %(card)s; color: %(card_text)s; }
  .card.big .n { font-size: calc(var(--val) * 1.9); font-weight: 800; color: %(big)s; line-height: 1;
    text-shadow: 0 6px 0 rgba(0,0,0,.15); font-family: 'Arial Black', '%(font)s', sans-serif; letter-spacing: -2px; }
  .card .l { font-size: var(--sub); font-weight: 800; line-height: 1.2; }
  .card.icon { background: linear-gradient(160deg, %(strip)s, %(strip2)s); color: #fff; }
  .card.icon .ic { width: 118px; height: 118px; filter: drop-shadow(0 10px 8px rgba(0,0,0,.4)); }
  .card.icon .v { font-size: var(--val); font-weight: 800; color: %(hl2)s; line-height: 1.1; }
  /* before -> after */
  .cmp { background: %(panel)s; border-radius: 30px; border: 5px solid #fff; box-shadow: 0 14px 30px rgba(0,0,0,.28);
    overflow: hidden; }
  .cmp h3 { background: %(panel_head)s; color: #fff; font-size: var(--sub); font-weight: 800; text-align: center;
    padding: 10px 16px; line-height: 1.2; }
  .cmp .row { display: grid; grid-template-columns: 1fr 150px 1fr; align-items: center; padding: 16px 20px 8px; }
  .cmp .side { text-align: center; }
  .cmp .side small { display: block; font-size: calc(var(--sub) * .8); font-weight: 800; color: #666; }
  .cmp .side b { display: block; font-size: var(--val); font-weight: 800; line-height: 1.15; color: #555;
    font-family: 'Arial Black', '%(font)s', sans-serif; }
  .cmp .side.now b { color: %(big)s; font-size: calc(var(--val) * 1.25); }
  .cmp .ic { width: 140px; height: 140px; justify-self: center; filter: drop-shadow(0 10px 8px rgba(0,0,0,.35)); }
  .cmp .chg { margin: 4px auto 16px; width: fit-content; padding: 6px 30px; border-radius: 40px; color: #fff;
    font-size: var(--sub); font-weight: 800; background: %(chg)s; }
  .strip { background: linear-gradient(90deg, %(strip2)s, %(strip)s); color: #fff; border-radius: 24px;
    padding: 16px 26px; font-size: var(--pt); font-weight: 700; line-height: 1.35; border: 4px solid #fff;
    box-shadow: 0 12px 26px rgba(0,0,0,.28); }
  .strip .num { color: %(hl2)s; }
  .lower { flex: 1; min-height: 420px; display: grid; grid-template-columns: %(cols)s; gap: 20px; }
  .panel { background: %(panel)s; border-radius: 28px; overflow: hidden; box-shadow: 0 14px 30px rgba(0,0,0,.28);
    display: flex; flex-direction: column; border: 4px solid #fff; }
  .panel h3 { background: %(panel_head)s; color: #fff; font-size: var(--sub); font-weight: 800; text-align: center;
    padding: 12px 16px; line-height: 1.2; }
  .panel ul { list-style: none; padding: 8px 20px; display: flex; flex-direction: column; justify-content: space-evenly;
    flex: 1; }
  .panel li { font-size: var(--pt); font-weight: 700; line-height: 1.3; padding: 10px 0; display: flex; gap: 14px;
    align-items: center; color: %(text)s; border-bottom: 2px dashed rgba(0,0,0,.12); }
  .panel li:last-child { border-bottom: 0; }
  .panel li .ic { width: 52px; height: 52px; flex-shrink: 0; }
  /* table / timeline rows */
  .panel table { width: 100%%; border-collapse: collapse; flex: 1; }
  .panel td { font-size: var(--pt); font-weight: 700; padding: 10px 18px; border-bottom: 2px solid rgba(0,0,0,.08);
    line-height: 1.25; }
  .panel tr:nth-child(even) td { background: rgba(0,0,0,.035); }
  .panel td:first-child { width: 46%%; }
  .panel td.r { text-align: right; font-weight: 800; color: %(big)s; font-size: calc(var(--pt) * 1.15);
    border-left: 2px solid rgba(0,0,0,.08); }
  .panel .tl { list-style: none; padding: 14px 20px 14px 34px; display: flex; flex-direction: column;
    justify-content: space-evenly; flex: 1; position: relative; }
  .panel .tl::before { content: ""; position: absolute; left: 55px; top: 30px; bottom: 30px; width: 6px;
    background: %(panel_head)s; border-radius: 3px; }
  .panel .tl li { border: 0; padding: 8px 0; }
  .panel .tl .dot { width: 48px; height: 48px; border-radius: 50%%; background: %(gold)s; border: 5px solid %(panel_head)s;
    color: #1a1a1a; font: 900 24px/38px Arial, sans-serif; text-align: center; flex-shrink: 0; z-index: 1; }
  .panel .tl b { color: %(big)s; }
  /* reasons: icon pills */
  .reasons { display: flex; flex-direction: column; justify-content: space-evenly; gap: 16px; }
  .reason { display: flex; align-items: center; gap: 18px; background: %(panel)s; border-radius: 80px 30px 30px 80px;
    padding: 12px 22px 12px 12px; box-shadow: 0 12px 26px rgba(0,0,0,.28); border: 4px solid #fff; }
  .reason .ic { width: 110px; height: 110px; flex-shrink: 0; background: radial-gradient(circle, #fff 0%%, %(card)s 100%%);
    border-radius: 50%%; padding: 10px; border: 4px solid %(panel_head)s; }
  .reason span { font-size: calc(var(--sub) * 1.15); font-weight: 800; line-height: 1.2; color: %(panel_head)s; }
  .num { color: %(big)s; font-weight: 800; }
  /* the picture: a cut-out object breaking out of its space, or a framed scene */
  .objcell { position: relative; min-height: 0; }
  .objcell .burst { position: absolute; inset: 5%% -10%% 0; border-radius: 50%%;
    background: radial-gradient(circle, rgba(255,230,140,.95) 0%%, rgba(255,200,60,.45) 35%%, transparent 68%%); }
  .objcell .obj { position: absolute; right: -26px; bottom: -12px; width: 116%%; height: 108%%; object-fit: contain;
    object-position: bottom center; filter: drop-shadow(0 26px 22px rgba(0,0,0,.5)); z-index: 5; }
  .objcell .big-ic { position: absolute; inset: 0; margin: auto; width: 82%%; max-height: 90%%; object-fit: contain;
    filter: drop-shadow(0 26px 22px rgba(0,0,0,.45)); }
  .pic { position: relative; border-radius: 28px; overflow: hidden; border: 6px solid #fff; min-height: 0;
    box-shadow: 0 14px 30px rgba(0,0,0,.35); background: %(strip)s center/cover no-repeat; }
  .pic .symbolic { position: absolute; right: 0; bottom: 0; background: rgba(0,0,0,.6); color: #fff; font-size: 22px;
    font-weight: 700; padding: 4px 14px; border-top-left-radius: 14px; }
  .cta { -webkit-mask-image: %(mask)s; -webkit-mask-size: 100%% 100%%; mask-image: %(mask)s; mask-size: 100%% 100%%;
    background: linear-gradient(90deg, %(strip2)s, %(strip)s); color: #fff; text-align: center; font-size: 54px;
    font-weight: 800; padding: 14px 40px 20px; line-height: 1.2; position: relative; z-index: 1; }
  .cta b { color: %(hl2)s; }
  .footer { display: flex; justify-content: space-between; font-size: 26px; font-weight: 700; color: %(fg)s; opacity: .9; }
"""


def _lines(headline: str, n: int) -> list[str]:
    """Split the headline into n lines of similar length, at word boundaries."""
    words = headline.split()
    n = max(1, min(n, len(words)))
    target = len(headline) / n
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + len(w) > target * 1.15 and len(lines) < n - 1:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur]


def _cta(text: str) -> str:
    """Last word(s) of the call-to-action in the highlight colour."""
    words = text.split()
    if len(words) < 2:
        return esc(text)
    return f'{esc(" ".join(words[:-1]))} <b>{esc(words[-1])}</b>'


def _headline(story) -> str:
    """Headline on painted strips; the highlight word or number is printed extra big."""
    n_lines = 2 if len(story.headline) < 34 else 3
    out = ""
    # the whole highlight if it fits on one line, else its number, else its longest word
    words = sorted(story.highlight.split(), key=lambda w: (not re.search(r"[\d૦-૯]", w), -len(w)))
    targets = [story.highlight] + words if story.highlight else []
    for line in _lines(story.headline, n_lines):
        text = esc(line)
        for word in targets:
            if word in line:
                text = text.replace(esc(word), f'<span class="hi">{esc(word)}</span>', 1)
                targets = []   # only one highlight on the whole headline
                break
        out += f"<div>{text}</div>"
    return out


def _cards(story) -> str:
    """Big-number card and a 3D-icon card from the facts."""
    facts = story.facts[:3]
    if not facts:
        return ""
    # the big card shows a short, number-led fact in full (never a number cut out of a longer value)
    big = next((f for f in facts if re.search(r"[\d૦-૯]", f["value"]) and len(f["value"]) <= 12), facts[0])
    other = next((f for f in facts if f is not big), None)
    size = "" if len(big["value"]) <= 9 else ' style="font-size:var(--val)"'
    cards = f'<div class="card big"><div class="l">{esc(big["label"])}</div><div class="n"{size}>{esc(big["value"])}</div></div>'
    if other:
        cards += (f'<div class="card icon">{icon_img(other["label"] + " " + other["value"])}'
                  f'<div class="l">{esc(other["label"])}</div><div class="v">{esc(other["value"])}</div></div>')
    return f'<div class="cards" style="grid-template-columns:{"1.15fr 1fr" if other else "1fr"}">{cards}</div>'


def _compare(story) -> str:
    c = story.compare
    down = c.get("direction") == "down"
    return (f'<div class="cmp"><h3>{esc(c.get("label") or story.kicker)}</h3><div class="row">'
            f'<div class="side"><small>પહેલાં</small><b>{esc(c["before"])}</b></div>'
            f'{icon_img("chart_down" if down else "chart_up")}'
            f'<div class="side now"><small>હવે</small><b>{esc(c["after"])}</b></div></div>'
            + (f'<div class="chg">{"▼" if down else "▲"} {esc(c["change"])}</div>' if c.get("change") else "")
            + "</div>")


def _visual_panel(story) -> str:
    """The left part of the lower area: table, timeline, reasons or checklist (by the story's visual)."""
    heading = esc(story.kicker or "મુખ્ય મુદ્દા")
    if story.visual == "table":
        rows = "".join(f'<tr><td>{esc(r["left"])}</td><td class="r">{esc(r["right"])}</td></tr>' for r in story.rows)
        return f'<div class="panel fit"><h3>{heading}</h3><table>{rows}</table></div>'
    if story.visual == "timeline":
        items = "".join(f'<li><span class="dot">{i}</span><span>{esc(r["left"])}: <b>{esc(r["right"])}</b></span></li>'
                        for i, r in enumerate(story.rows, 1))
        return f'<div class="panel fit"><h3>{heading}</h3><ul class="tl">{items}</ul></div>'
    if story.visual == "reasons":
        items = "".join(f'<div class="reason">{icon_img(r.get("icon") or r["text"])}<span>{esc(r["text"])}</span></div>'
                        for r in story.reasons)
        return f'<div class="reasons fit">{items}</div>'
    points = story.points[:5]
    if len(points) < 2:
        return ""
    items = "".join(f'<li>{icon_img("check")}<span>{highlight_numbers(p)}</span></li>' for p in points)
    return f'<div class="panel fit"><h3>{heading}</h3><ul>{items}</ul></div>'


def bulletin_page(story, font: str, image_url: str | None, date: str, handle: str, mood: str,
                  cutout_url: str | None = None) -> str:
    labels, palettes = MOOD_LOOK.get(mood, MOOD_LOOK["info"])
    pal = PALETTES[random.choice(palettes)]
    panel = _visual_panel(story)
    cols = "1.3fr 1fr" if panel else "1fr"
    chg = "#d00000" if story.compare.get("direction") == "down" else "#2b9348"
    css = CSS % {**pal, "font": font, "mask": BRUSH_MASK, "cols": cols, "chg": chg}

    top = _compare(story) if story.visual == "compare" else _cards(story)
    # with the compare box the facts are already shown; a short summary strip explains the story
    strip = (f'<div class="strip fit">{highlight_numbers(story.summary)}</div>'
             if story.visual in ("compare", "reasons") and story.summary else "")
    if cutout_url:
        pic = f'<div class="objcell"><div class="burst"></div><img class="obj" src="{cutout_url}" alt=""></div>'
    elif image_url:
        pic = f'<div class="pic" style="background-image:url({image_url})"><div class="symbolic">પ્રતિકાત્મક તસવીર</div></div>'
    else:
        pic = f'<div class="objcell"><div class="burst"></div>{icon_img(story.headline, "big-ic")}</div>'

    font_url = font.replace(" ", "+")
    corners = ('<div class="corner" style="left:-190px; top:60px"></div>'
               '<div class="corner" style="right:-190px; bottom:330px"></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family={font_url}:wght@500;700;800&display=block" rel="stylesheet">
<style>{css}</style></head><body>{corners}
  <div id="main">
    <div class="label">{"".join(f"<span>{esc(t)}</span>" for t in labels)}</div>
    <div class="hl">{_headline(story)}</div>
    {f'<div class="sub">{esc(story.subheadline)}</div>' if story.subheadline else ""}
    {top}
    {strip}
    <div class="lower">{panel}{pic}</div>
    <div class="cta">{_cta(story.cta or "વધુ અપડેટ માટે ફોલો કરો")}</div>
    <div class="footer"><span>સ્રોત: {esc(story.source_name)} • {date}</span><span>{esc(handle)}</span></div>
  </div></body></html>"""
