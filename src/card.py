"""Render the news card (1080x1920 PNG) from an HTML template with headless Chromium."""
import base64
import html
import random
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from .news import IST, NewsStory

WIDTH, HEIGHT = 1080, 1920

# Several colour themes per category; one is picked at random so the feed doesn't look repetitive.
# banner: top ribbon, accent: borders/strips, glow: light behind the centre, base: background gradient.
THEMES = {
    "crime": [
        {"tag": "🔴 BREAKING", "icon": "🚨", "banner": "linear-gradient(90deg,#b00000,#ff1f1f,#b00000)",
         "accent": "#ff2e2e", "glow": "rgba(255,40,40,.55)", "base": "linear-gradient(170deg,#3d0000,#120000 55%,#2a0505)"},
        {"tag": "🔴 ક્રાઇમ એલર્ટ", "icon": "🚔", "banner": "linear-gradient(90deg,#7a0019,#e0002a,#7a0019)",
         "accent": "#ff4d6d", "glow": "rgba(224,0,42,.5)", "base": "linear-gradient(170deg,#1a0010,#0a0006 55%,#2b0016)"},
    ],
    "good_news": [
        {"tag": "🟢 ખુશખબર", "icon": "🎉", "banner": "linear-gradient(90deg,#007f3f,#1fcf6b,#007f3f)",
         "accent": "#2ee87a", "glow": "rgba(46,232,122,.45)", "base": "linear-gradient(170deg,#003d24,#001a10 55%,#004d2e)"},
        {"tag": "🌟 સારા સમાચાર", "icon": "🏆", "banner": "linear-gradient(90deg,#006d77,#14b8a6,#006d77)",
         "accent": "#5eead4", "glow": "rgba(20,184,166,.5)", "base": "linear-gradient(170deg,#00343a,#00161a 55%,#023e44)"},
    ],
    "government": [
        {"tag": "📢 સરકારી અપડેટ", "icon": "🏛️", "banner": "linear-gradient(90deg,#c2410c,#ff8a00,#c2410c)",
         "accent": "#ff9f1c", "glow": "rgba(255,138,0,.45)", "base": "linear-gradient(170deg,#0b1f4d,#050d24 55%,#13306b)"},
        {"tag": "📢 મોટા સમાચાર", "icon": "📜", "banner": "linear-gradient(90deg,#1d4ed8,#3b82f6,#1d4ed8)",
         "accent": "#60a5fa", "glow": "rgba(59,130,246,.5)", "base": "linear-gradient(170deg,#0a1a3f,#040b1f 55%,#122a66)"},
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
  /* sunburst rays + centre glow give the plain theme some energy */
  .rays {{ position: absolute; inset: -400px;
    background: repeating-conic-gradient(from 0deg at 50% 50%, rgba(255,255,255,.06) 0deg 6deg, transparent 6deg 18deg);
    -webkit-mask: radial-gradient(circle at 50% 50%, #000 0%, transparent 60%); }}
  .glow {{ position: absolute; left: 50%; top: 50%; width: 1100px; height: 1100px; transform: translate(-50%,-50%);
    background: radial-gradient(circle, {glow} 0%, transparent 65%); }}
  .photo {{ position: absolute; inset: 0; background-position: center; background-size: cover; }}
  .shade {{ position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,.6) 0%, rgba(0,0,0,.3) 28%, rgba(0,0,0,0) 42%,
                rgba(0,0,0,0) 60%, rgba(0,0,0,.55) 78%, rgba(0,0,0,.8) 100%); }}
  .icon {{ position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%); font-size: 300px;
    filter: drop-shadow(0 20px 40px rgba(0,0,0,.6)); opacity: .9; }}
  .edge {{ position: absolute; inset: 0; border: 14px solid {accent}; pointer-events: none;
    box-shadow: inset 0 0 60px rgba(0,0,0,.6); }}
  #main {{ position: absolute; inset: 0; padding: 0 56px 64px; display: flex; flex-direction: column; gap: 34px; }}
  .banner {{ margin: 0 -56px; background: {banner}; padding: 34px 40px 30px; text-align: center;
    border-bottom-left-radius: 60px; border-bottom-right-radius: 60px; box-shadow: 0 14px 40px rgba(0,0,0,.55); }}
  .tag {{ display: inline-block; background: #fff; color: #111; font-size: 34px; font-weight: 800;
    padding: 6px 26px; border-radius: 40px; margin-bottom: 14px; }}
  .kicker {{ font-size: 58px; font-weight: 800; line-height: 1.2; text-shadow: 0 4px 12px rgba(0,0,0,.5); }}
  .headline {{ font-size: var(--hl, 132px); font-weight: 800; line-height: 1.1; text-align: center; color: #ffe100;
    text-shadow: 0 8px 0 #000, 0 0 30px rgba(0,0,0,.9); -webkit-text-stroke: 4px #000; paint-order: stroke fill; }}
  .sub {{ align-self: center; background: #fff; color: #111; padding: 18px 34px; border-radius: 20px;
    font-size: var(--sub, 50px); font-weight: 800; line-height: 1.3; text-align: center;
    box-shadow: 0 10px 30px rgba(0,0,0,.5); border-bottom: 10px solid {accent}; }}
  .spacer {{ flex: 1; }}
  .facts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  .fact {{ background: rgba(8,10,25,.86); border: 5px solid {accent}; border-radius: 26px; padding: 20px 16px;
    text-align: center; display: flex; flex-direction: column; justify-content: center; gap: 4px;
    box-shadow: 0 0 28px {glow}; }}
  .fact.wide {{ grid-column: span 2; }}
  .fact .label {{ font-size: 40px; font-weight: 700; color: #fff; }}
  .fact .value {{ font-size: var(--val, 68px); font-weight: 800; color: #ffe100; line-height: 1.15; }}
  .cta {{ background: linear-gradient(90deg,#ffd000,#ffe94d,#ffd000); color: #111; font-size: 46px; font-weight: 800;
    padding: 22px 30px; border-radius: 20px; text-align: center; line-height: 1.3; box-shadow: 0 10px 30px rgba(0,0,0,.5); }}
  .footer {{ display: flex; justify-content: space-between; font-size: 32px; color: #f1f3f5; font-weight: 700;
    text-shadow: 0 2px 8px #000; }}
</style></head>
<body>
  <div class="rays"></div>
  <div class="glow"></div>
  {background}
  <div class="shade"></div>
  <div class="edge"></div>
  <div id="main">
    <div class="banner"><div class="tag">{tag}</div><div class="kicker">{kicker}</div></div>
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
  let hl = 132, sub = 50, val = 68;
  const overflow = () => main.scrollHeight > main.clientHeight + 1;
  while (overflow() && hl > 64) {
    hl -= 4; sub = Math.max(38, sub - 1); val = Math.max(44, val - 2);
    root.setProperty('--hl', hl + 'px'); root.setProperty('--sub', sub + 'px'); root.setProperty('--val', val + 'px');
  }
  return !overflow();
}"""


def _gujarati_date(now: datetime) -> str:
    return f"{now.day} {GUJARATI_MONTHS[now.month - 1]} {now.year}"


def render_card(story: NewsStory, cfg: dict, out_path: Path, background: Path | None = None) -> Path:
    theme = random.choice(THEMES.get(story.category, THEMES["government"]))
    esc = html.escape
    facts = story.facts[:4]
    fact_html = "".join(
        f'<div class="fact{" wide" if len(facts) % 2 and i == len(facts) - 1 else ""}">'
        f'<div class="label">{esc(f["label"])}</div><div class="value">{esc(f["value"])}</div></div>'
        for i, f in enumerate(facts)
    )
    if background:
        mime = "image/png" if background.suffix.lower() == ".png" else "image/jpeg"
        data = base64.b64encode(background.read_bytes()).decode()
        background_html = f'<div class="photo" style="background-image:url(data:{mime};base64,{data})"></div>'
    else:
        background_html = f'<div class="icon">{theme["icon"]}</div>'

    font = cfg["card"]["font"]
    page_html = TEMPLATE.format(
        w=WIDTH, h=HEIGHT, font=font, font_url=font.replace(" ", "+"),
        base=theme["base"], banner=theme["banner"], accent=theme["accent"], glow=theme["glow"],
        background=background_html, tag=esc(theme["tag"]), kicker=esc(story.kicker), headline=esc(story.headline),
        subheadline=esc(story.subheadline), facts=fact_html, cta=esc(story.cta), source=esc(story.source_name),
        date=_gujarati_date(datetime.now(IST)), handle=esc(cfg["card"]["handle"]),
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
