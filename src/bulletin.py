"""Bulletin design, modelled on Gemini-made Gujarati news posters: a two-colour slanted label on top, the
headline on painted strips, a big-number card and an icon card, a checklist next to the AI picture, and a
painted call-to-action strip at the bottom. The picture comes from the image AI (no text in it); every
Gujarati word is real text in a real font, so it is always spelled right.
"""
import random

from src.designs import BRUSH_MASK, FIT_SCRIPT, big_number, esc, highlight_numbers, icon_for

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
  #main { position: absolute; inset: 40px 34px 30px; display: flex; flex-direction: column; gap: 22px; z-index: 2; }
  #main > * { flex-shrink: 0; }
  #main > .lower { flex-shrink: 1; }
  .label { display: flex; flex-direction: column; align-items: center; transform: skew(-8deg); }
  .label span { font-weight: 800; font-size: 82px; line-height: 1.08; padding: 0 34px; color: #fff;
    background: %(strip)s; border: 5px solid #fff; box-shadow: 8px 8px 0 rgba(0,0,0,.35); }
  .label span + span { background: %(gold)s; color: #1a1a1a; margin-top: -6px; margin-left: 120px; }
  .hl { display: flex; flex-direction: column; align-items: center; gap: 10px; }
  .hl div { -webkit-mask-image: %(mask)s; -webkit-mask-size: 100%% 100%%; mask-image: %(mask)s; mask-size: 100%% 100%%;
    background: linear-gradient(180deg, %(strip)s, %(strip2)s); color: %(hl)s; font-size: var(--hl); font-weight: 800;
    line-height: 1.22; padding: 8px 46px 14px; text-align: center; text-shadow: 0 5px 0 rgba(0,0,0,.45);
    max-width: 100%%; white-space: nowrap; overflow: hidden; }
  .hl div:nth-child(even) { color: %(hl2)s; }
  .sub { text-align: center; font-size: var(--sub); font-weight: 800; color: %(fg)s; line-height: 1.25; }
  .cards { display: grid; grid-template-columns: 1.15fr 1fr; gap: 22px; }
  .card { border-radius: 30px; padding: 20px 24px; display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center; box-shadow: 0 14px 30px rgba(0,0,0,.28); border: 5px solid #fff; }
  .card.big { background: %(card)s; color: %(card_text)s; }
  .card.big .n { font-size: calc(var(--val) * 1.9); font-weight: 800; color: %(big)s; line-height: 1;
    text-shadow: 0 6px 0 rgba(0,0,0,.15); font-family: 'Arial Black', '%(font)s', sans-serif; letter-spacing: -2px; }
  .card .l { font-size: var(--sub); font-weight: 800; line-height: 1.2; }
  .card.icon { background: linear-gradient(160deg, %(strip)s, %(strip2)s); color: #fff; }
  .card.icon .e { font-size: 110px; line-height: 1.1; filter: drop-shadow(0 8px 6px rgba(0,0,0,.4)); }
  .card.icon .v { font-size: var(--val); font-weight: 800; color: %(hl2)s; line-height: 1.1; }
  .lower { flex: 1; min-height: 420px; display: grid; grid-template-columns: %(cols)s; gap: 20px; }
  .panel { background: %(panel)s; border-radius: 28px; overflow: hidden; box-shadow: 0 14px 30px rgba(0,0,0,.28);
    display: flex; flex-direction: column; border: 4px solid #fff; }
  .panel h3 { background: %(panel_head)s; color: #fff; font-size: var(--sub); font-weight: 800; text-align: center;
    padding: 12px 16px; line-height: 1.2; }
  .panel ul { list-style: none; padding: 8px 20px; display: flex; flex-direction: column; justify-content: space-evenly;
    flex: 1; }
  .panel li { font-size: var(--pt); font-weight: 700; line-height: 1.3; padding: 10px 0 10px 58px; position: relative;
    color: %(text)s; border-bottom: 2px dashed rgba(0,0,0,.12); }
  .panel li:last-child { border-bottom: 0; }
  .panel li::before { content: "✓"; font-family: Arial, sans-serif; font-weight: 900; position: absolute; left: 0; top: 10px; width: 44px; height: 44px; border-radius: 50%%;
    background: #2b9348; color: #fff; font-size: 28px; display: flex; align-items: center; justify-content: center; }
  .num { color: %(big)s; font-weight: 800; }
  .pic { position: relative; border-radius: 28px; overflow: hidden; border: 6px solid #fff; min-height: 0;
    box-shadow: 0 14px 30px rgba(0,0,0,.35); background: %(strip)s center/cover no-repeat; }
  .pic .symbolic { position: absolute; right: 0; bottom: 0; background: rgba(0,0,0,.6); color: #fff; font-size: 22px;
    font-weight: 700; padding: 4px 14px; border-top-left-radius: 14px; }
  .pic .emo { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 220px; }
  .cta { -webkit-mask-image: %(mask)s; -webkit-mask-size: 100%% 100%%; mask-image: %(mask)s; mask-size: 100%% 100%%;
    background: linear-gradient(90deg, %(strip2)s, %(strip)s); color: #fff; text-align: center; font-size: 54px;
    font-weight: 800; padding: 14px 40px 20px; line-height: 1.2; }
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


def bulletin_page(story, font: str, image_url: str | None, date: str, handle: str, mood: str) -> str:
    labels, palettes = MOOD_LOOK.get(mood, MOOD_LOOK["info"])
    pal = PALETTES[random.choice(palettes)]
    points = story.points[:5]
    cols = "1.25fr 1fr" if len(points) >= 2 else "1fr"
    css = (CSS % {**pal, "font": font, "mask": BRUSH_MASK, "cols": cols})

    facts = story.facts[:2]
    number = big_number(story)
    big_label = next((f["label"] for f in story.facts if number and number in f["value"]), facts[0]["label"] if facts else "")
    if not number and facts:
        number = facts[0]["value"]
    other = next((f for f in facts if f["label"] != big_label), None)
    cards = ""
    if number:
        cards += f'<div class="card big"><div class="l">{esc(big_label)}</div><div class="n">{esc(number)}</div></div>'
    if other:
        cards += (f'<div class="card icon"><div class="e">{icon_for(other["label"] + " " + other["value"])}</div>'
                  f'<div class="l">{esc(other["label"])}</div><div class="v">{esc(other["value"])}</div></div>')
    cards_html = f'<div class="cards" style="grid-template-columns:{"1.15fr 1fr" if number and other else "1fr"}">{cards}</div>' if cards else ""

    n_lines = 2 if len(story.headline) < 34 else 3
    headline = "".join(f"<div>{esc(line)}</div>" for line in _lines(story.headline, n_lines))
    panel = ""
    if len(points) >= 2:
        heading = esc(story.kicker or "મુખ્ય મુદ્દા")
        items = "".join(f"<li>{highlight_numbers(p)}</li>" for p in points)
        panel = f'<div class="panel fit"><h3>{heading}</h3><ul>{items}</ul></div>'
    if image_url:
        pic = f'<div class="pic" style="background-image:url({image_url})"><div class="symbolic">પ્રતિકાત્મક તસવીર</div></div>'
    else:
        pic = f'<div class="pic"><div class="emo">{icon_for(story.headline)}</div></div>'

    font_url = font.replace(" ", "+")
    corners = ('<div class="corner" style="left:-190px; top:60px"></div>'
               '<div class="corner" style="right:-190px; bottom:330px"></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family={font_url}:wght@500;700;800&display=block" rel="stylesheet">
<style>{css}</style></head><body>{corners}
  <div id="main">
    <div class="label">{"".join(f"<span>{esc(t)}</span>" for t in labels)}</div>
    <div class="hl">{headline}</div>
    {f'<div class="sub">{esc(story.subheadline)}</div>' if story.subheadline else ""}
    {cards_html}
    <div class="lower">{panel}{pic}</div>
    <div class="cta">{_cta(story.cta or "વધુ અપડેટ માટે ફોલો કરો")}</div>
    <div class="footer"><span>સ્રોત: {esc(story.source_name)} • {date}</span><span>{esc(handle)}</span></div>
  </div></body></html>"""
