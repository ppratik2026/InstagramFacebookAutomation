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

from . import designs
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
        {"tag": "📢 મોટા સમાચાર", "scene": ["📣", "🗞️", "🏛️"], "banner": "linear-gradient(90deg,#9d0208,#e85d04,#9d0208)",
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


# Infographic layout (like viral Gujarati news posters): headline box, highlight strip, picture with a stamp
# on the left, a checklist of points on the right, call-to-action strip at the bottom.
INFO_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family={font_url}:wght@500;700;800&display=block" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ width: {w}px; height: {h}px; overflow: hidden; }}
  body {{ font-family: '{font}', 'Noto Sans Gujarati', 'Noto Color Emoji', sans-serif; color: #fff;
    background: {base}; position: relative; }}
  .rays {{ position: absolute; inset: -500px;
    background: repeating-conic-gradient(from 0deg at 50% 50%, rgba(255,255,255,.06) 0deg 5deg, transparent 5deg 15deg);
    -webkit-mask: radial-gradient(circle at 50% 50%, #000 0%, transparent 55%); }}
  .bokeh {{ position: absolute; border-radius: 50%; background: {bokeh}; filter: blur(2px); }}
  #main {{ position: absolute; inset: 0; padding: 34px 34px 30px; display: flex; flex-direction: column; gap: 20px; }}
  .head {{ background: linear-gradient(180deg, #0d1b4c, #08112e); border: 5px solid {accent}; border-radius: 34px;
    padding: 18px 24px 26px; text-align: center; box-shadow: 0 0 40px {glow}, 0 18px 40px rgba(0,0,0,.6); }}
  .tag {{ display: inline-block; background: {banner}; padding: 6px 28px; border-radius: 30px; font-size: 38px;
    font-weight: 800; margin-bottom: 8px; }}
  .headline {{ font-size: var(--hl, 108px); font-weight: 800; line-height: 1.08;
    -webkit-text-stroke: 5px #000; paint-order: stroke fill; text-shadow: 0 6px 0 #000, 0 0 30px rgba(0,0,0,.7); }}
  .headline .a {{ color: #fff; }}
  .headline .b {{ color: #ffd60a; }}
  .strip {{ background: linear-gradient(90deg, #ffc300, #ffe14d, #ffc300); color: #111; border-radius: 22px;
    padding: 16px 24px; text-align: center; font-size: var(--sub, 48px); font-weight: 800; line-height: 1.25;
    box-shadow: 0 10px 26px rgba(0,0,0,.5); border: 4px solid #000; }}
  .num {{ display: inline-block; background: #d90429; color: #fff; padding: 0 .25em; margin: 0 .08em; border-radius: .18em; }}
  .mid {{ flex: 1; min-height: 0; display: flex; gap: 20px; }}
  .left {{ width: 46%; display: flex; flex-direction: column; gap: 16px; }}
  .pic {{ flex: 1; min-height: 0; position: relative; border-radius: 30px; overflow: hidden; border: 5px solid #fff;
    background: radial-gradient(circle at 50% 45%, {glow}, rgba(0,0,0,.35) 70%); box-shadow: 0 16px 34px rgba(0,0,0,.6); }}
  .pic .img {{ position: absolute; inset: 0; background-size: cover; background-position: center; }}
  .pic .emoji {{ position: absolute; left: 50%; top: 45%; transform: translate(-50%,-50%); font-size: 220px;
    filter: drop-shadow(0 20px 30px rgba(0,0,0,.6)); }}
  .symbolic {{ position: absolute; left: 0; top: 0; z-index: 2; background: #d90429; color: #fff; font-size: 24px;
    font-weight: 800; padding: 6px 16px; border-bottom-right-radius: 14px; }}
  .stamp {{ position: absolute; left: 50%; bottom: 14%; transform: translateX(-50%) rotate(-14deg);
    border: 8px solid #d00000; color: #d00000; background: rgba(255,255,255,.88); border-radius: 14px;
    padding: 4px 26px; font: 900 64px/1.1 'Arial Black', Impact, sans-serif; letter-spacing: 3px; white-space: nowrap;
    text-transform: uppercase; box-shadow: 0 8px 24px rgba(0,0,0,.5); }}
  .chip {{ background: linear-gradient(180deg, #0d1b4c, #08112e); border: 4px solid {accent}; border-radius: 22px;
    padding: 12px 14px; text-align: center; }}
  .chip .label {{ font-size: 32px; font-weight: 700; color: #dfe7ff; }}
  .chip .value {{ font-size: 44px; font-weight: 800; color: #ffd60a; line-height: 1.15; }}
  .right {{ flex: 1; background: rgba(255,255,255,.95); color: #10183a; border-radius: 30px; padding: 22px 22px;
    display: flex; flex-direction: column; justify-content: space-evenly; gap: 10px; box-shadow: 0 16px 34px rgba(0,0,0,.55); }}
  .pt {{ display: flex; gap: 12px; align-items: flex-start; font-size: var(--pt, 36px); font-weight: 700; line-height: 1.3;
    padding-bottom: 10px; border-bottom: 2px solid #e3e7f2; }}
  .pt:last-child {{ border-bottom: none; padding-bottom: 0; }}
  .pt.sum b {{ color: #d90429; }}
  .pt .tick {{ flex: none; width: 1.15em; height: 1.15em; border-radius: 50%; background: #1fa64a; color: #fff;
    display: flex; align-items: center; justify-content: center; font-size: .8em; margin-top: .1em; }}
  .cta {{ background: linear-gradient(90deg, #9d0208, #e5383b, #9d0208); border-radius: 26px; padding: 18px 24px;
    text-align: center; font-size: 50px; font-weight: 800; line-height: 1.2; border: 4px solid #ffd60a;
    box-shadow: 0 12px 30px rgba(0,0,0,.55); text-shadow: 0 3px 0 rgba(0,0,0,.4); }}
  .footer {{ display: flex; justify-content: space-between; font-size: 30px; font-weight: 700; color: #eef1f6;
    text-shadow: 0 2px 6px #000; }}
</style></head>
<body>
  <div class="rays"></div>
  {bokeh_html}
  <div id="main">
    <div class="head"><div class="tag">{tag} • {kicker}</div><div class="headline">{headline}</div></div>
    <div class="strip">{subheadline}</div>
    <div class="mid">
      <div class="left"><div class="pic">{picture}{stamp}</div>{chips}</div>
      <div class="right">{points}</div>
    </div>
    <div class="cta">{cta}</div>
    <div class="footer"><span>સ્રોત: {source} • {date}</span><span>{handle}</span></div>
  </div>
</body></html>
"""

INFO_FIT_SCRIPT = """() => {
  const main = document.getElementById('main');
  const right = document.querySelector('.right');
  const root = document.documentElement.style;
  let hl = 108, sub = 48, pt = 36;
  const overflow = () => main.scrollHeight > main.clientHeight + 1 || right.scrollHeight > right.clientHeight + 1;
  while (overflow() && (hl > 64 || pt > 24)) {
    if (hl > 64) hl -= 4;
    if (pt > 24) pt -= 1;
    sub = Math.max(36, sub - 1);
    root.setProperty('--hl', hl + 'px'); root.setProperty('--sub', sub + 'px'); root.setProperty('--pt', pt + 'px');
  }
  return !overflow();
}"""


# Intro animation for the reel: elements fly / punch / slam in one after another. Each element keeps its own
# transform (--t0) so rotated stickers end exactly where the static design has them.
ANIM_CSS = """<style>
@keyframes dropIn { from { transform: translateY(-160%) var(--t0); opacity: 0; } to { transform: var(--t0); opacity: 1; } }
@keyframes punchIn { 0% { transform: scale(2.6) var(--t0); opacity: 0; } 60% { transform: scale(.92) var(--t0); opacity: 1; }
  100% { transform: var(--t0); } }
@keyframes zoomIn { from { transform: scale(1.35) var(--t0); opacity: 0; } to { transform: var(--t0); opacity: 1; } }
@keyframes slam { 0% { transform: var(--t0) scale(4); opacity: 0; } 55% { transform: var(--t0) scale(.88); opacity: 1; }
  75% { transform: var(--t0) scale(1.08); } 100% { transform: var(--t0); } }
@keyframes slideL { from { transform: translateX(-130%) var(--t0); } to { transform: var(--t0); } }
@keyframes slideR { from { transform: translateX(130%) var(--t0); } to { transform: var(--t0); } }
@keyframes popIn { 0% { transform: scale(0) var(--t0); opacity: 0; } 70% { transform: scale(1.12) var(--t0); opacity: 1; }
  100% { transform: var(--t0); } }
@keyframes riseUp { from { transform: translateY(160%) var(--t0); opacity: 0; } to { transform: var(--t0); opacity: 1; } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes flash { from { opacity: .95; } to { opacity: 0; } }
@keyframes shake { 0%, 100% { translate: 0 0; } 20% { translate: -14px 6px; } 40% { translate: 12px -8px; }
  60% { translate: -8px 4px; } 80% { translate: 6px -2px; } }
#flash { position: fixed; inset: 0; background: #fff; z-index: 99; pointer-events: none; }
</style>"""

# [selector, animation, start s, duration s, stagger s]; each element animates once (first match wins)
ANIM_JS = """(steps) => {
  const done = new Set();
  for (const [sel, name, start, dur, stagger] of steps) {
    [...document.querySelectorAll(sel)].filter(el => !done.has(el)).forEach((el, i) => {
      done.add(el);
      const t0 = getComputedStyle(el).transform;
      el.style.setProperty('--t0', t0 === 'none' ? 'translate(0)' : t0);
      const anim = name === 'slideAlt' ? (i % 2 ? 'slideR' : 'slideL') : name;
      el.style.animation = `${anim} ${dur}s cubic-bezier(.2,.9,.3,1.2) ${start + i * stagger}s both`;
    });
  }
  const flash = document.createElement('div'); flash.id = 'flash';
  flash.style.animation = 'flash .35s ease-out 0s both'; document.body.appendChild(flash);
  const main = document.getElementById('main');
  if (main) main.style.animation = 'shake .3s linear 1.55s both';   // the stamp "hits" the poster
  document.getAnimations().forEach(a => a.pause());
}"""

ANIM_STEPS = [
    [".head", "zoomIn", 0.0, 0.4, 0],
    [".banner, .pill, .tag, .kicker", "dropIn", 0.05, 0.45, 0],
    [".h3d, .headline", "punchIn", 0.3, 0.6, 0],
    [".photo, .img, .fallback, .scene, .icon, .pic", "zoomIn", 0.7, 0.7, 0],
    [".sub, .strip", "slideL", 1.0, 0.45, 0],
    [".summary", "slideR", 1.1, 0.45, 0],
    [".stamp, .callout", "slam", 1.3, 0.45, 0],
    [".sticker, .stk", "popIn", 1.45, 0.35, 0.25],
    [".sash", "slideL", 0.2, 0.4, 0],
    [".bar, .box, .fact, .chip, .card", "slideAlt", 1.5, 0.4, 0.15],
    [".checks .side", "popIn", 1.9, 0.35, 0.2],
    [".glass, .right, .pts, .why, .panel", "fadeIn", 1.9, 0.25, 0],
    [".pt", "popIn", 2.0, 0.35, 0.14],
    [".ribbon", "slideR", 2.6, 0.4, 0],
    [".cta, .bottom", "riseUp", 2.8, 0.45, 0],
    [".footer", "fadeIn", 3.0, 0.3, 0],
]


def _capture_intro(page, frames_dir: Path, seconds: float, fps: int) -> None:
    """Screenshot the intro animation frame by frame (deterministic, no screen recording)."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    page.add_style_tag(content=ANIM_CSS.removeprefix("<style>").removesuffix("</style>"))
    page.evaluate(ANIM_JS, ANIM_STEPS)
    for n in range(int(seconds * fps)):
        page.evaluate("t => document.getAnimations().forEach(a => a.currentTime = t)", n * 1000 / fps)
        page.screenshot(path=str(frames_dir / f"f{n:04d}.jpg"), type="jpeg", quality=92)


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


def _data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _info_page(story: NewsStory, cfg: dict, theme: dict, image: Path | None, font: str) -> str:
    esc = html.escape
    picture = (f'<div class="img" style="background-image:url({_data_url(image)})"></div>' if image
               else f'<div class="emoji">{theme["scene"][0]}</div>')
    stamp = f'<div class="stamp">{esc(story.stamp)}</div>' if story.stamp else ""
    if image:
        stamp = designs.SYMBOLIC + stamp
    chips = "".join(f'<div class="chip"><div class="label">{esc(f["label"])}</div>'
                    f'<div class="value">{esc(f["value"])}</div></div>' for f in story.facts[:2])
    points = "".join(f'<div class="pt"><span class="tick">✓</span><span>{esc(p)}</span></div>' for p in story.points[:5])
    if story.summary:
        points = f'<div class="pt sum"><span><b>શું થયું?</b> {esc(story.summary)}</span></div>' + points
    return INFO_TEMPLATE.format(
        w=WIDTH, h=HEIGHT, font=font, font_url=font.replace(" ", "+"), base=theme["base"], banner=theme["banner"],
        accent=theme["accent"], glow=theme["glow"], bokeh=theme["bokeh"], bokeh_html=_bokeh(), tag=esc(theme["tag"]),
        kicker=esc(story.kicker), headline=_two_tone(story.headline),
        subheadline=designs.highlight_numbers(story.subheadline), picture=picture, stamp=stamp, chips=chips, points=points, cta=esc(story.cta), source=esc(story.source_name),
        date=_gujarati_date(datetime.now(IST)), handle=esc(cfg["card"]["handle"]),
    )


def render_card(story: NewsStory, cfg: dict, out_path: Path, background: Path | None = None,
                intro_dir: Path | None = None) -> Path:
    """Render the card PNG. With intro_dir, also write the intro animation frames there."""
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
    if font == "random":
        font = random.choice(designs.FONTS)
    # pick one of the designs that suits this story, so the feed doesn't look repetitive
    # the design follows the news mood (breaking / money / info / happy), picked at random among the fitting ones
    mood = designs.mood_of(story)
    allowed = cfg["card"].get("designs", ["mag", "hero", "split", "paper"])
    options = [d for d in designs.MOODS[mood]["designs"] if d in allowed
               and not (d == "split" and len(story.points) < 3) and not (d == "hero" and not background)]
    design = random.choice(options or [d for d in allowed if d != "hero" or background] or ["classic"])
    print(f"   Mood: {mood}")
    print(f"   Design: {design}")
    fit_script = FIT_SCRIPT
    date = _gujarati_date(datetime.now(IST))
    image_url = _data_url(background) if background else None
    if design == "hero":
        layout = designs.hero_layout(background)
        print(f"   Layout: {layout} (text placed away from the picture's subject)")
        page_html = designs.hero_page(story, theme, font, image_url, date, cfg["card"]["handle"], layout)
        fit_script = designs.FIT_SCRIPT
    elif design == "mag":
        page_html = designs.mag_page(story, theme, font, image_url, date, cfg["card"]["handle"], mood)
        fit_script = designs.FIT_SCRIPT
    elif design == "paper":
        page_html = designs.paper_page(story, theme, font, image_url, date, cfg["card"]["handle"])
        fit_script = designs.FIT_SCRIPT
    elif design == "split":
        page_html = _info_page(story, cfg, theme, background, font)
        fit_script = INFO_FIT_SCRIPT
    else:
        page_html = TEMPLATE.format(
            w=WIDTH, h=HEIGHT, font=font, font_url=font.replace(" ", "+"),
            base=theme["base"], banner=theme["banner"], accent=theme["accent"], glow=theme["glow"], bokeh=theme["bokeh"],
            bokeh_html=_bokeh(), background=background_html, tag=esc(theme["tag"]), kicker=esc(story.kicker),
            headline=_two_tone(story.headline), subheadline=esc(story.subheadline), facts=fact_html, cta=esc(story.cta),
            source=esc(story.source_name), date=_gujarati_date(datetime.now(IST)), handle=esc(cfg["card"]["handle"]),
        )
    if cfg["card"].get("stickers", True):
        page_html = page_html.replace("</body>", designs.decor_html(mood) + "</body>", 1)
    (out_path.parent / "card.html").write_text(page_html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.set_content(page_html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        if not page.evaluate(fit_script):
            print("Warning: card text is too long and may be cut off.")
        page.screenshot(path=str(out_path))
        if intro_dir:
            vcfg = cfg["video"]
            _capture_intro(page, intro_dir, vcfg.get("intro_seconds", 3.4), vcfg["fps"])
        browser.close()
    return out_path
