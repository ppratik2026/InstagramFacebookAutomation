"""Render the news card (1080x1920 PNG) from an HTML template with headless Chromium.

This is the fixed-design card: used when card.style is "template", and as the fallback when the
AI poster fails its proof-read.
"""
import base64
import html
import random
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from .news import IST, NewsStory

WIDTH, HEIGHT = 1080, 1920

# Several colour themes per category; one is picked at random so the feed doesn't look repetitive.
# banner: top ribbon, accent: borders/strips, glow: light behind the centre, base: background gradient,
# scene: emoji "illustration" used when there is no background image.
THEMES = {
    "crime": [
        {"tag": "🔴 BREAKING", "scene": ["🚔", "🚨", "🔍"], "banner": "linear-gradient(90deg,#8b0000,#ff1f1f,#8b0000)",
         "accent": "#ff2e2e", "glow": "rgba(255,40,40,.6)", "bokeh": "#ff4d4d",
         "base": "radial-gradient(circle at 50% 42%,#7a0000 0%,#2b0000 45%,#0a0000 100%)"},
        {"tag": "🔴 ક્રાઇમ એલર્ટ", "scene": ["👮", "🚨", "⛓️"], "banner": "linear-gradient(90deg,#4a0020,#e0002a,#4a0020)",
         "accent": "#ff4d6d", "glow": "rgba(224,0,42,.55)", "bokeh": "#4dabff",
         "base": "radial-gradient(circle at 50% 42%,#3d0a2b 0%,#14040f 50%,#05060f 100%)"},
    ],
    "good_news": [
        {"tag": "🟢 ખુશખબર", "scene": ["🏆", "🎉", "⭐"], "banner": "linear-gradient(90deg,#00632f,#1fcf6b,#00632f)",
         "accent": "#ffd23f", "glow": "rgba(255,210,63,.5)", "bokeh": "#ffe066",
         "base": "radial-gradient(circle at 50% 42%,#0b7a45 0%,#03381f 50%,#011a0e 100%)"},
        {"tag": "🌟 સારા સમાચાર", "scene": ["🎊", "🚀", "🌟"], "banner": "linear-gradient(90deg,#00565e,#14b8a6,#00565e)",
         "accent": "#5eead4", "glow": "rgba(94,234,212,.5)", "bokeh": "#a7f3d0",
         "base": "radial-gradient(circle at 50% 42%,#0e7c86 0%,#033a40 50%,#011a1d 100%)"},
    ],
    "government": [
        {"tag": "📢 સરકારી અપડેટ", "scene": ["🏛️", "📜", "✅"], "banner": "linear-gradient(90deg,#b23a00,#ff8a00,#b23a00)",
         "accent": "#ff9f1c", "glow": "rgba(255,138,0,.55)", "bokeh": "#ffb347",
         "base": "radial-gradient(circle at 50% 42%,#1e3a8a 0%,#0b1a45 50%,#040a1f 100%)"},
        {"tag": "📢 મોટા સમાચાર", "scene": ["📣", "📅", "💰"], "banner": "linear-gradient(90deg,#9d0208,#e85d04,#9d0208)",
         "accent": "#ffba08", "glow": "rgba(255,186,8,.55)", "bokeh": "#ffd166",
         "base": "radial-gradient(circle at 50% 42%,#e85d04 0%,#9d0208 40%,#370617 100%)"},
    ],
}

GUJARATI_MONTHS = ["જાન્યુઆરી", "ફેબ્રુઆરી", "માર્ચ", "એપ્રિલ", "મે", "જૂન",
                   "જુલાઈ", "ઑગસ્ટ", "સપ્ટેમ્બર", "ઑક્ટોબર", "નવેમ્બર", "ડિસેમ્બર"]

TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family={font_url}:wght@500;700;800&display=block" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {w}px; height: {h}px; overflow: hidden; }}
  body {{
    font-family: '{font}', 'Noto Sans Gujarati', 'Noto Color Emoji', sans-serif;
    background: {base}; color: #fff; position: relative;
  }}
  .rays {{ position: absolute; inset: -500px;
    background: repeating-conic-gradient(from 0deg at 50% 50%, rgba(255,255,255,.07) 0deg 5deg, transparent 5deg 15deg);
    -webkit-mask: radial-gradient(circle at 50% 50%, #000 0%, transparent 55%); }}
  .glow {{ position: absolute; left: 50%; top: 52%; width: 1200px; height: 1200px; transform: translate(-50%,-50%);
    background: radial-gradient(circle, {glow} 0%, transparent 62%); }}
  .streak {{ position: absolute; left: -200px; right: -200px; height: 120px; transform: rotate(-24deg);
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.10), transparent); }}
  .bokeh {{ position: absolute; border-radius: 50%; background: {bokeh}; filter: blur(2px); }}
  .photo {{ position: absolute; inset: 0; background-position: center; background-size: cover; }}
  .shade {{ position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,.6) 0%, rgba(0,0,0,.3) 28%, rgba(0,0,0,0) 42%,
                rgba(0,0,0,0) 60%, rgba(0,0,0,.55) 78%, rgba(0,0,0,.8) 100%); }}
  .scene {{ position: absolute; left: 0; right: 0; top: 50%; height: 0; }}
  .scene span {{ position: absolute; transform: translate(-50%,-50%);
    filter: drop-shadow(0 26px 30px rgba(0,0,0,.65)) drop-shadow(0 0 40px {glow}); }}
  .floor {{ position: absolute; left: 50%; top: 50%; width: 640px; height: 90px; transform: translate(-50%, 150px);
    background: radial-gradient(ellipse, rgba(0,0,0,.55), transparent 70%); }}
  .edge {{ position: absolute; inset: 16px; border: 6px solid {accent}; border-radius: 34px; pointer-events: none;
    box-shadow: 0 0 30px {glow}, inset 0 0 30px {glow}; }}
  #main {{ position: absolute; inset: 0; padding: 0 60px 70px; display: flex; flex-direction: column; gap: 30px; }}
  .banner {{ margin: 0 -60px; background: {banner}; padding: 40px 50px 34px; text-align: center; position: relative;
    clip-path: polygon(0 0, 100% 0, 100% 78%, 50% 100%, 0 78%); box-shadow: 0 14px 40px rgba(0,0,0,.55); }}
  .kicker {{ font-size: 60px; font-weight: 800; line-height: 1.15; text-shadow: 0 4px 0 rgba(0,0,0,.35); }}
  .sticker {{ position: absolute; top: 150px; right: 34px; background: #fff; color: #c1121f; font-size: 34px; font-weight: 800;
    padding: 10px 26px; border-radius: 16px; transform: rotate(8deg); box-shadow: 0 8px 20px rgba(0,0,0,.5);
    border: 4px solid {accent}; z-index: 2; }}
  .headline {{ margin-top: 40px; font-size: var(--hl, 136px); font-weight: 800; line-height: 1.08; text-align: center;
    -webkit-text-stroke: 6px #000; paint-order: stroke fill;
    text-shadow: 0 6px 0 #000, 0 12px 0 rgba(0,0,0,.55), 0 0 40px rgba(0,0,0,.8); }}
  .headline .a {{ color: #fff; }}
  .headline .b {{ color: #ffe14d; }}
  .sub {{ align-self: center; background: #fff; color: #111; padding: 16px 36px; border-radius: 18px;
    font-size: var(--sub, 50px); font-weight: 800; line-height: 1.3; text-align: center; transform: rotate(-1.5deg);
    box-shadow: 0 12px 30px rgba(0,0,0,.5), 8px 8px 0 {accent}; }}
  .spacer {{ flex: 1; }}
  .facts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .fact {{ border-radius: 28px; padding: 5px; background: linear-gradient(135deg, {accent}, #fff6, {accent});
    box-shadow: 0 0 34px {glow}, 0 16px 30px rgba(0,0,0,.5); }}
  .fact > div {{ height: 100%; border-radius: 24px; padding: 20px 16px; text-align: center;
    background: linear-gradient(180deg, rgba(20,22,45,.92), rgba(5,6,18,.95));
    display: flex; flex-direction: column; justify-content: center; gap: 4px; }}
  .fact.wide {{ grid-column: span 2; }}
  .fact .label {{ font-size: 40px; font-weight: 700; color: #f1f3f5; }}
  .fact .value {{ font-size: var(--val, 70px); font-weight: 800; color: #ffe14d; line-height: 1.12;
    text-shadow: 0 4px 0 #000; }}
  .cta {{ background: linear-gradient(90deg,#ffc300,#fff176,#ffc300); color: #111; font-size: 46px; font-weight: 800;
    padding: 22px 30px; border-radius: 22px; text-align: center; line-height: 1.3; transform: rotate(-1deg);
    box-shadow: 0 12px 30px rgba(0,0,0,.55); border: 4px solid #000; }}
  .footer {{ display: flex; justify-content: space-between; font-size: 32px; color: #f1f3f5; font-weight: 700;
    text-shadow: 0 2px 8px #000; }}
</style></head>
<body>
  <div class="rays"></div>
  <div class="glow"></div>
  <div class="streak" style="top:620px"></div>
  <div class="streak" style="top:1180px; opacity:.6"></div>
  {bokeh_html}
  {background}
  <div class="edge"></div>
  <div class="sticker">{tag}</div>
  <div id="main">
    <div class="banner"><div class="kicker">{kicker}</div></div>
    <div class="headline">{headline}</div>
    <div class="sub">{subheadline}</div>
    <div class="spacer"></div>
    <div class="facts">{facts}</div>
    <div class="cta">{cta}</div>
    <div class="footer"><span>સ્રોત: {source} • {date}</span><span>{handle}</span></div>
  </div>
</body></html>
"""

# Shrink the big text until everything fits in one screen.
FIT_SCRIPT = """() => {
  const main = document.getElementById('main');
  const root = document.documentElement.style;
  let hl = 136, sub = 50, val = 70;
  const overflow = () => main.scrollHeight > main.clientHeight + 1;
  while (overflow() && hl > 64) {
    hl -= 4; sub = Math.max(38, sub - 1); val = Math.max(44, val - 2);
    root.setProperty('--hl', hl + 'px'); root.setProperty('--sub', sub + 'px'); root.setProperty('--val', val + 'px');
  }
  return !overflow();
}"""


def _gujarati_date(now: datetime) -> str:
    return f"{now.day} {GUJARATI_MONTHS[now.month - 1]} {now.year}"


def _two_tone(headline: str) -> str:
    """First part of the headline in white, the rest in yellow, like viral news posters."""
    words = headline.split()
    cut = max(1, len(words) * 2 // 5) if len(words) > 1 else 0
    first, rest = " ".join(words[:cut]), " ".join(words[cut:])
    out = f'<span class="a">{html.escape(first)}</span><br>' if first else ""
    return out + f'<span class="b">{html.escape(rest)}</span>'


def _bokeh() -> str:
    dots = []
    for _ in range(40):
        size = random.randint(6, 34)
        dots.append(
            f'<div class="bokeh" style="left:{random.randint(0, WIDTH)}px;top:{random.randint(300, HEIGHT)}px;'
            f'width:{size}px;height:{size}px;opacity:{random.uniform(.15, .6):.2f}"></div>'
        )
    return "".join(dots)


def _scene(icons: list[str]) -> str:
    big, left, right = icons[0], icons[1], icons[2]
    return (
        '<div class="floor"></div><div class="scene">'
        f'<span style="left:50%;top:0;font-size:330px">{big}</span>'
        f'<span style="left:20%;top:70px;font-size:190px;transform:translate(-50%,-50%) rotate(-12deg)">{left}</span>'
        f'<span style="left:80%;top:60px;font-size:190px;transform:translate(-50%,-50%) rotate(12deg)">{right}</span>'
        '</div>'
    )


def render_card(story: NewsStory, cfg: dict, out_path: Path, background: Path | None = None) -> Path:
    theme = random.choice(THEMES.get(story.category, THEMES["government"]))
    esc = html.escape
    facts = story.facts[:4]
    fact_html = "".join(
        f'<div class="fact{" wide" if len(facts) % 2 and i == len(facts) - 1 else ""}"><div>'
        f'<div class="label">{esc(f["label"])}</div><div class="value">{esc(f["value"])}</div></div></div>'
        for i, f in enumerate(facts)
    )
    if background:
        mime = "image/png" if background.suffix.lower() == ".png" else "image/jpeg"
        data = base64.b64encode(background.read_bytes()).decode()
        background_html = (f'<div class="photo" style="background-image:url(data:{mime};base64,{data})"></div>'
                           '<div class="shade"></div>')
    else:
        background_html = _scene(theme["scene"])

    font = cfg["card"]["font"]
    page_html = TEMPLATE.format(
        w=WIDTH, h=HEIGHT, font=font, font_url=font.replace(" ", "+"),
        base=theme["base"], banner=theme["banner"], accent=theme["accent"], glow=theme["glow"], bokeh=theme["bokeh"],
        bokeh_html=_bokeh(), background=background_html, tag=esc(theme["tag"]), kicker=esc(story.kicker),
        headline=_two_tone(story.headline), subheadline=esc(story.subheadline), facts=fact_html, cta=esc(story.cta),
        source=esc(story.source_name), date=_gujarati_date(datetime.now(IST)), handle=esc(cfg["card"]["handle"]),
    )
    (out_path.parent / "card.html").write_text(page_html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(page_html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        if not page.evaluate(FIT_SCRIPT):
            print("Warning: card text is too long and may be cut off.")
        page.screenshot(path=str(out_path))
        browser.close()
    return out_path
