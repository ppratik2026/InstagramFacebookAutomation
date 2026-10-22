"""Render the news card (1080x1920 PNG) from an HTML template with headless Chromium."""
import base64
import html
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from .news import IST, NewsStory

WIDTH, HEIGHT = 1080, 1920

THEMES = {
    "crime": {"accent": "#e5383b", "icon": "🚨", "bg": "linear-gradient(160deg,#2b0a0a,#120606 60%,#3a0d0d)"},
    "good_news": {"accent": "#2dc653", "icon": "✅", "bg": "linear-gradient(160deg,#06281a,#04130d 60%,#0b3d26)"},
    "government": {"accent": "#ff8800", "icon": "📢", "bg": "linear-gradient(160deg,#0b1d3a,#060f1f 60%,#13305e)"},
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
    background: {bg}; color: #fff; position: relative;
  }}
  .photo {{ position: absolute; inset: 0; background-position: center; background-size: cover; }}
  .shade {{ position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,.55) 0%, rgba(0,0,0,.35) 35%, rgba(0,0,0,.75) 70%, rgba(0,0,0,.9) 100%); }}
  #main {{ position: absolute; inset: 0; padding: 90px 60px 70px; display: flex; flex-direction: column; gap: 42px; }}
  .kicker {{ align-self: center; background: {accent}; padding: 14px 44px; border-radius: 22px;
    font-size: 54px; font-weight: 800; box-shadow: 0 10px 30px rgba(0,0,0,.45); text-align: center; }}
  .headline {{ font-size: var(--hl, 128px); font-weight: 800; line-height: 1.12; text-align: center; color: #ffd60a;
    text-shadow: 0 6px 0 #000, 0 0 24px rgba(0,0,0,.8); -webkit-text-stroke: 3px #000; paint-order: stroke fill; }}
  .sub {{ background: rgba(0,0,0,.72); border-left: 12px solid {accent}; padding: 22px 28px; border-radius: 14px;
    font-size: var(--sub, 52px); font-weight: 700; line-height: 1.3; text-align: center; }}
  .facts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 26px; }}
  .fact {{ background: rgba(10,14,30,.82); border: 4px solid {accent}; border-radius: 24px; padding: 22px 18px;
    text-align: center; display: flex; flex-direction: column; justify-content: center; gap: 6px; }}
  .fact.wide {{ grid-column: span 2; }}
  .fact .label {{ font-size: 40px; font-weight: 600; color: #e9ecef; }}
  .fact .value {{ font-size: var(--val, 66px); font-weight: 800; color: #ffd60a; line-height: 1.15; }}
  .spacer {{ flex: 1; }}
  .spacer.top {{ flex: 0.6; }}
  .cta {{ background: #ffd60a; color: #111; font-size: 46px; font-weight: 800; padding: 22px 30px;
    border-radius: 18px; text-align: center; line-height: 1.3; }}
  .footer {{ display: flex; justify-content: space-between; font-size: 32px; color: #dee2e6; font-weight: 600; }}
</style></head>
<body>
  {photo_div}
  <div class="shade"></div>
  <div id="main">
    <div class="kicker">{icon} {kicker} {icon}</div>
    <div class="spacer top"></div>
    <div class="headline">{headline}</div>
    <div class="sub">{subheadline}</div>
    <div class="facts">{facts}</div>
    <div class="spacer"></div>
    <div class="cta">{cta}</div>
    <div class="footer"><span>સ્રોત: {source} • {date}</span><span>{handle}</span></div>
  </div>
</body></html>
"""

# Shrink the big text until everything fits in one screen.
FIT_SCRIPT = """() => {
  const main = document.getElementById('main');
  const root = document.documentElement.style;
  let hl = 128, sub = 52, val = 66;
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
    theme = THEMES.get(story.category, THEMES["government"])
    esc = html.escape
    facts = story.facts[:4]
    fact_html = "".join(
        f'<div class="fact{" wide" if len(facts) % 2 and i == len(facts) - 1 else ""}">'
        f'<div class="label">{esc(f["label"])}</div><div class="value">{esc(f["value"])}</div></div>'
        for i, f in enumerate(facts)
    )
    photo_div = ""
    if background:
        data = base64.b64encode(background.read_bytes()).decode()
        photo_div = f'<div class="photo" style="background-image:url(data:image/jpeg;base64,{data})"></div>'

    font = cfg["card"]["font"]
    page_html = TEMPLATE.format(
        w=WIDTH, h=HEIGHT, font=font, font_url=font.replace(" ", "+"), bg=theme["bg"], accent=theme["accent"],
        photo_div=photo_div, icon=theme["icon"], kicker=esc(story.kicker), headline=esc(story.headline),
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
