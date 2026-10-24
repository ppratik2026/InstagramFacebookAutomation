"""Premium card designs inspired by viral Gujarati news posters.

hero:  full-screen AI picture, big 3D headline, glowing fact bars, glass panel of points, ribbons.
paper: light newspaper-infographic look with a huge red headline and red info boxes.
Both share the 3D headline, number highlighting and the generic fit script.
"""
import html
import re

esc = html.escape

# Shrinks the --hl / --sub / --pt / --val sizes until #main (and every .fit box) fits.
FIT_SCRIPT = """() => {
  const main = document.getElementById('main');
  const root = document.documentElement.style;
  const v = {hl: 124, sub: 46, pt: 34, val: 60};
  const set = () => { for (const k in v) root.setProperty('--' + k, v[k] + 'px'); };
  // Gujarati vowel signs poke a few px past the line box; that is not a real overflow
  const over = el => el.scrollHeight > el.clientHeight + 12;
  const overflow = () => over(main) || [...document.querySelectorAll('.fit')].some(over);
  set();
  while (overflow() && (v.hl > 60 || v.pt > 22)) {
    if (v.hl > 60) v.hl -= 4;
    if (v.pt > 22) v.pt -= 1;
    v.sub = Math.max(32, v.sub - 1); v.val = Math.max(36, v.val - 2);
    set();
  }
  return !overflow();
}"""

COMMON_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { width: 1080px; height: 1920px; overflow: hidden; }
  body { font-family: '%(font)s', 'Noto Sans Gujarati', 'Noto Color Emoji', sans-serif; position: relative; }
  /* 3D headline: a thick black stroked copy behind, a gradient-filled copy on top */
  .h3d { display: grid; text-align: center; font-size: var(--hl); font-weight: 800; line-height: 1.08; }
  .h3d > span { grid-area: 1 / 1; }
  .h3d .back { color: #000; -webkit-text-stroke: 18px #000; text-shadow: 0 12px 0 #000, 0 22px 40px rgba(0,0,0,.65); }
  .h3d .front .a { color: #fff; }
  .h3d .front .b { background: linear-gradient(180deg, #fffbd0 0%%, #ffe14d 35%%, #ffb700 70%%, #ff8c00 100%%);
    -webkit-background-clip: text; background-clip: text; color: transparent; }
  .num { display: inline-block; background: #d90429; color: #fff; padding: 0 .25em; margin: 0 .08em; border-radius: .18em;
    box-shadow: 0 .08em 0 rgba(0,0,0,.35); }
  .stamp { position: absolute; transform: rotate(-12deg); border: 9px solid #d00000; color: #d00000;
    background: rgba(255,255,255,.9); border-radius: 16px; padding: 4px 30px; white-space: nowrap; z-index: 3;
    font: 900 74px/1.1 'Arial Black', Impact, sans-serif; letter-spacing: 4px; text-transform: uppercase;
    box-shadow: 0 10px 30px rgba(0,0,0,.55); outline: 3px solid rgba(208,0,0,.5); outline-offset: 6px; }
  .footer { display: flex; justify-content: space-between; font-size: 30px; font-weight: 700; }
  .symbolic { position: absolute; left: 0; top: 0; z-index: 2; background: #d90429; color: #fff; font-size: 26px;
    font-weight: 800; padding: 6px 18px; border-bottom-right-radius: 16px; }
  #main > * { flex-shrink: 0; }   /* only the picture area (flex: 1) may shrink; text never gets squeezed */
  #main > .pic, #main > .hero-space { flex-shrink: 1; }
"""

HEAD = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family={font_url}:wght@500;700;800&display=block" rel="stylesheet">
<style>{css}</style></head><body>"""


def hero_layout(image_path) -> str:
    """Pick where the text goes from where the picture's subject is (most detail), so text sits on quiet areas.

    split: subject in the middle -> headline on top, info at the bottom
    bottom: subject in the upper part -> all text at the bottom
    top: subject in the lower part -> all text at the top
    side-left / side-right: subject on one side -> text column on the other side
    """
    import random
    if image_path is None:
        return random.choice(["split", "bottom", "top"])
    from PIL import Image, ImageFilter, ImageStat
    img = Image.open(image_path).convert("L").resize((60, 108)).filter(ImageFilter.FIND_EDGES)
    w, h = img.size
    def energy(box):
        return ImageStat.Stat(img.crop(box)).mean[0] + 1e-6
    top, mid, bot = (energy((0, 0, w, h // 3)), energy((0, h // 3, w, 2 * h // 3)), energy((0, 2 * h // 3, w, h)))
    left, right = energy((0, h // 5, w // 2, 4 * h // 5)), energy((w // 2, h // 5, w, 4 * h // 5))
    options = []
    if left > right * 1.35:
        options.append("side-right")       # subject on the left -> text on the right
    if right > left * 1.35:
        options.append("side-left")
    if top > max(mid, bot) * 1.15:
        options.append("bottom")
    if bot > max(mid, top) * 1.15:
        options.append("top")
    if mid >= max(top, bot):
        options.append("split")
    return random.choice(options or ["split", "bottom", "top"])


SYMBOLIC = '<div class="symbolic">પ્રતિકાત્મક તસવીર</div>'


def headline_3d(headline: str) -> str:
    """Two-tone 3D headline: first ~40% of the words white, the rest gold."""
    words = headline.split()
    cut = max(1, len(words) * 2 // 5) if len(words) > 1 else 0
    first, rest = " ".join(words[:cut]), " ".join(words[cut:])
    inner = (f'<span class="a">{esc(first)}</span><br>' if first else "") + f'<span class="b">{esc(rest)}</span>'
    return f'<div class="h3d"><span class="back">{inner}</span><span class="front">{inner}</span></div>'


def highlight_numbers(text: str) -> str:
    """Escape text and put words with digits (times, amounts, dates) in red boxes."""
    return re.sub(r"(\S*[\d૦-૯]\S*)", r'<span class="num">\1</span>', esc(text))


# Gujarati Google Fonts with heavy weights; one is picked per post for variety.
FONTS = ["Baloo Bhai 2", "Hind Vadodara", "Mukta Vaani", "Anek Gujarati", "Noto Sans Gujarati"]

# Fill of the coloured part of the 3D headline; one is picked per post.
HEADLINE_FILLS = [
    "linear-gradient(180deg, #fffbd0 0%, #ffe14d 35%, #ffb700 70%, #ff8c00 100%)",   # gold
    "linear-gradient(180deg, #ffd6d6 0%, #ff4d4d 45%, #c1121f 100%)",                # red
    "linear-gradient(180deg, #e0fbff 0%, #5ee7ff 45%, #0096c7 100%)",                # cyan
    "linear-gradient(180deg, #fff 0%, #ffe8a3 50%, #ffc300 100%)",                   # white-gold
    "linear-gradient(180deg, #e9ffdb 0%, #7cff6b 45%, #19a974 100%)",                # green
]

SUMMARY_CSS = """
  .summary { background: rgba(255,255,255,.94); color: #10183a; border-radius: 24px; padding: 16px 22px;
    font-size: var(--pt); font-weight: 700; line-height: 1.35; box-shadow: 0 12px 30px rgba(0,0,0,.4);
    border-left: 12px solid %(accent)s; }
  .summary b { display: block; font-size: 1.05em; font-weight: 800; color: #d90429; margin-bottom: 4px; }
"""


def summary_box(story) -> str:
    if not story.summary:
        return ""
    return f'<div class="summary fit"><b>શું થયું?</b>{esc(story.summary)}</div>'


def _head(font: str, css: str, accent: str = "#ffb703", fill: str | None = None) -> str:
    import random
    fill = fill or random.choice(HEADLINE_FILLS)
    extra = (SUMMARY_CSS % {"accent": accent}).replace("%%", "%")
    return HEAD.format(font_url=font.replace(" ", "+"),
                       css=(COMMON_CSS % {"font": font}) + css + extra + f"\n  .h3d .front .b {{ background-image: {fill}; }}\n")


def _sparks(color: str, n: int = 45) -> str:
    import random
    return "".join(
        f'<i class="spark" style="left:{random.randint(0, 1080)}px;top:{random.randint(250, 1900)}px;'
        f'width:{(s := random.randint(4, 14))}px;height:{s}px;opacity:{random.uniform(.3, .9):.2f};'
        f'background:{color};box-shadow:0 0 {s * 2}px {color}"></i>'
        for _ in range(n)
    )


HERO_CSS = """
  body { background: #05060f; color: #fff; }
  .img { position: absolute; inset: 0; background-size: cover; background-position: center top; filter: saturate(1.25) contrast(1.05); }
  .fallback { position: absolute; inset: 0; background: %(base)s; }
  .fallback b { position: absolute; left: 50%%; top: 47%%; transform: translate(-50%%,-50%%); font-size: 380px;
    filter: drop-shadow(0 30px 40px rgba(0,0,0,.6)) drop-shadow(0 0 60px %(glow)s); }
  .shade { position: absolute; inset: 0; background:
    linear-gradient(180deg, rgba(0,0,0,.88) 0%%, rgba(0,0,0,.55) 24%%, rgba(0,0,0,0) 38%%, rgba(0,0,0,0) 50%%,
                    rgba(0,0,0,.65) 64%%, rgba(0,0,0,.92) 100%%),
    radial-gradient(ellipse at 50%% 45%%, transparent 40%%, rgba(0,0,0,.45) 100%%); }
  .spark { position: absolute; border-radius: 50%%; }
  .frame { position: absolute; inset: 14px; border: 5px solid %(accent)s; border-radius: 36px;
    box-shadow: 0 0 40px %(glow)s, inset 0 0 40px %(glow)s; pointer-events: none; }
  #main { position: absolute; inset: 0; padding: 46px 46px 40px; display: flex; flex-direction: column; gap: 22px; }
  .banner { align-self: center; background: rgba(20,0,0,.6); border: 4px solid %(accent)s; border-radius: 40px;
    padding: 10px 40px; font-size: 52px; font-weight: 800; box-shadow: 0 0 30px %(glow)s; backdrop-filter: blur(6px); }
  .hero-space { flex: 1; min-height: 460px; position: relative; }   /* the picture always stays visible */
  body.side-left .hero-space, body.side-right .hero-space { min-height: 0; }
  .hero-space .symbolic { border-radius: 12px; }
  .hero-space .stamp { left: 50%%; top: 50%%; transform: translate(-50%%,-50%%) rotate(-12deg); }
  .bar { background: linear-gradient(90deg, rgba(30,0,5,.9), rgba(60,5,10,.85)); border: 4px solid #ffb703;
    border-radius: 26px; padding: 14px 26px; text-align: center; font-size: var(--val); font-weight: 800; line-height: 1.15;
    box-shadow: 0 0 30px rgba(255,183,3,.45), 0 14px 30px rgba(0,0,0,.5); }
  .bar .l { color: #fff; } .bar .v { color: #ffd60a; }
  .glass { background: rgba(10,14,35,.72); border: 3px solid rgba(255,255,255,.35); border-radius: 30px;
    padding: 18px 26px; backdrop-filter: blur(10px); display: flex; flex-direction: column; gap: 10px; }
  .pt { display: flex; gap: 14px; align-items: flex-start; font-size: var(--pt); font-weight: 700; line-height: 1.3; }
  .pt i { flex: none; width: 1.1em; height: 1.1em; margin-top: .12em; border-radius: 50%%; font-style: normal;
    background: linear-gradient(180deg, #ffe14d, #ff9f1c); color: #111; display: flex; align-items: center;
    justify-content: center; font-size: .75em; font-weight: 900; }
  .ribbon { margin: 0 -46px; background: linear-gradient(90deg, transparent, #c1121f 12%%, #e5383b 50%%, #c1121f 88%%, transparent);
    padding: 14px 60px; text-align: center; font-size: var(--sub); font-weight: 800; text-shadow: 0 3px 0 rgba(0,0,0,.4); }
  .cta { background: linear-gradient(90deg, #ffc300, #fff176, #ffc300); color: #111; border-radius: 20px; padding: 16px 24px;
    text-align: center; font-size: 44px; font-weight: 800; border: 4px solid #000; transform: rotate(-1deg);
    box-shadow: 0 12px 30px rgba(0,0,0,.6); }
  .footer { color: #eef1f6; text-shadow: 0 2px 6px #000; }
  .side-stamp { position: absolute; bottom: 9%%; z-index: 3; width: 31%%; display: flex; justify-content: center; }
  .side-stamp .stamp { position: static; font-size: 46px; padding: 2px 16px; border-width: 6px; }
  /* layouts: where the dark shade (and the text) sits depends on where the picture's subject is */
  body.bottom .shade { background: linear-gradient(180deg, rgba(0,0,0,.55) 0%%, rgba(0,0,0,0) 14%%, rgba(0,0,0,0) 36%%,
    rgba(0,0,0,.8) 52%%, rgba(0,0,0,.94) 100%%); }
  body.top .shade { background: linear-gradient(180deg, rgba(0,0,0,.94) 0%%, rgba(0,0,0,.8) 48%%, rgba(0,0,0,0) 64%%,
    rgba(0,0,0,0) 82%%, rgba(0,0,0,.85) 100%%); }
  body.side-left .shade { background: linear-gradient(90deg, rgba(0,0,0,.94) 0%%, rgba(0,0,0,.82) 55%%, rgba(0,0,0,0) 78%%); }
  body.side-right .shade { background: linear-gradient(270deg, rgba(0,0,0,.94) 0%%, rgba(0,0,0,.82) 55%%, rgba(0,0,0,0) 78%%); }
  body.side-left #main { right: 33%%; padding-right: 10px; }
  body.side-right #main { left: 33%%; padding-left: 10px; }
  body.side-left .side-stamp { right: 1%%; } body.side-right .side-stamp { left: 1%%; }
  body.side-left .ribbon, body.side-right .ribbon { margin: 0; border-radius: 18px; background: #c1121f; }
  body.side-left .banner, body.side-right .banner { font-size: 40px; padding: 8px 24px; }
"""


def hero_page(story, theme: dict, font: str, image_url: str | None, date: str, handle: str,
              layout: str = "split") -> str:
    picture = (f'<div class="img" style="background-image:url({image_url})"></div>' if image_url
               else f'<div class="fallback"><b>{theme["scene"][0]}</b></div>')
    stamp = f'<div class="stamp">{esc(story.stamp)}</div>' if story.stamp else ""
    symbolic = SYMBOLIC if image_url else ""
    banner = f'<div class="banner">{esc(theme["tag"].split(" ", 1)[0])} {esc(story.kicker)}</div>'
    head = headline_3d(story.headline)
    bars = "".join(f'<div class="bar"><span class="l">{esc(f["label"])}: </span><span class="v">{esc(f["value"])}</span></div>'
                   for f in story.facts[:2])
    points = ""
    if story.points:
        points = '<div class="glass fit">' + "".join(
            f'<div class="pt"><i>✓</i><span>{esc(p)}</span></div>' for p in story.points[:3]) + "</div>"
    summary = summary_box(story)
    ribbon = f'<div class="ribbon">{highlight_numbers(story.subheadline)}</div>'
    cta = f'<div class="cta">{esc(story.cta)}</div>'
    footer = f'<div class="footer"><span>સ્રોત: {esc(story.source_name)} • {date}</span><span>{esc(handle)}</span></div>'
    space = f'<div class="hero-space">{symbolic}{stamp}</div>'
    order = {
        "split": [banner, head, space, ribbon, summary, bars, points, cta, footer],
        "bottom": [banner, space, head, ribbon, summary, bars, points, cta, footer],
        "top": [banner, head, ribbon, summary, bars, points, space, cta, footer],
    }
    extra = ""
    if layout.startswith("side"):
        blocks = [banner, head, ribbon, summary, bars, points, '<div class="hero-space"></div>', cta, footer]
        extra = f'<div class="side-stamp">{stamp}</div>{symbolic}'
    else:
        blocks = order.get(layout, order["split"])
    css = HERO_CSS % {"accent": theme["accent"], "glow": theme["glow"], "base": theme["base"]}
    page = _head(font, css, theme["accent"]) + f"""
  {picture}<div class="shade"></div>{_sparks(theme["bokeh"])}{extra}
  <div id="main">{"".join(blocks)}</div></body></html>"""
    return page.replace("<body>", f'<body class="{layout}">', 1)


PAPER_CSS = """
  body { color: #111; background:
    radial-gradient(circle at 1px 1px, rgba(0,0,0,.07) 1.5px, transparent 0) 0 0 / 22px 22px,
    linear-gradient(180deg, #fffdf7, #f3efe4); }
  .topbar { position: absolute; left: 0; right: 0; top: 0; height: 18px; background: %(accent)s; }
  #main { position: absolute; inset: 0; padding: 50px 44px 38px; display: flex; flex-direction: column; gap: 20px; }
  .tag { align-self: flex-start; background: #d90429; color: #fff; font-size: 40px; font-weight: 800; padding: 8px 26px;
    border-radius: 0 22px 22px 0; margin-left: -44px; box-shadow: 0 8px 18px rgba(0,0,0,.25); }
  .h3d .back { color: #fff; -webkit-text-stroke: 16px #fff; text-shadow: 0 10px 0 #7a0000, 0 18px 30px rgba(0,0,0,.35); }
  .h3d .front .a { color: #111; }
  .h3d .front .b { background: linear-gradient(180deg, #ff4d4d, #d90429 55%%, #8b0000); -webkit-background-clip: text;
    background-clip: text; color: transparent; }
  .sub { font-size: var(--sub); font-weight: 800; text-align: center; line-height: 1.3; }
  .pic { flex: 1; min-height: 260px; position: relative; border-radius: 30px; overflow: hidden; border: 6px solid #111;
    box-shadow: 0 16px 34px rgba(0,0,0,.3); background: radial-gradient(circle at 50%% 45%%, %(glow)s, #1b1b2f 75%%); }
  .pic .img { position: absolute; inset: 0; background-size: cover; background-position: center top; }
  .pic b { position: absolute; left: 50%%; top: 50%%; transform: translate(-50%%,-50%%); font-size: 260px; }
  .pic .stamp { right: 30px; bottom: 34px; }
  .boxes { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .box { background: linear-gradient(180deg, #e01e37, #a4161a); color: #fff; border-radius: 22px; padding: 14px 18px;
    text-align: center; box-shadow: 0 10px 22px rgba(164,22,26,.35); border: 4px solid #fff; outline: 3px solid #a4161a; }
  .box .l { font-size: 32px; font-weight: 700; opacity: .95; }
  .box .v { font-size: var(--val); font-weight: 800; line-height: 1.12; }
  .why { font-size: calc(var(--pt) * 1.6); font-weight: 800; border-left: 14px solid #d90429; padding-left: 16px; }
  .summary { border-left-color: #d90429; }
  .pts { display: flex; flex-direction: column; gap: 8px; }
  .pt { display: flex; gap: 12px; font-size: var(--pt); font-weight: 700; line-height: 1.3; }
  .pt i { color: #d90429; font-style: normal; flex: none; }
  .cta { background: #111; color: #ffd60a; border-radius: 18px; padding: 16px 24px; text-align: center; font-size: 44px;
    font-weight: 800; }
  .footer { color: #333; }
"""


def paper_page(story, theme: dict, font: str, image_url: str | None, date: str, handle: str) -> str:
    picture = (f'<div class="img" style="background-image:url({image_url})"></div>' if image_url
               else f'<b>{theme["scene"][0]}</b>')
    stamp = f'<div class="stamp">{esc(story.stamp)}</div>' if story.stamp else ""
    boxes = "".join(f'<div class="box"><div class="l">{esc(f["label"])}</div><div class="v">{esc(f["value"])}</div></div>'
                    for f in story.facts[:2])
    points = ""
    if story.points:
        points = ('<div class="why">મુખ્ય મુદ્દા</div><div class="pts fit">'
                  + "".join(f'<div class="pt"><i>▶</i><span>{esc(p)}</span></div>' for p in story.points[:3]) + "</div>")
    css = PAPER_CSS % {"accent": theme["accent"], "glow": theme["glow"]}
    red = "linear-gradient(180deg, #ff4d4d, #d90429 55%, #8b0000)"
    return _head(font, css, theme["accent"], fill=red) + f"""
  <div class="topbar"></div>
  <div id="main">
    <div class="tag">{esc(theme["tag"])} • {esc(story.kicker)}</div>
    {headline_3d(story.headline)}
    <div class="sub">{highlight_numbers(story.subheadline)}</div>
    {summary_box(story)}
    <div class="pic">{picture}{SYMBOLIC if image_url else ""}{stamp}</div>
    <div class="boxes">{boxes}</div>
    {points}
    <div class="cta">{esc(story.cta)}</div>
    <div class="footer"><span>સ્રોત: {esc(story.source_name)} • {date}</span><span>{esc(handle)}</span></div>
  </div></body></html>"""


def icon_for(text: str) -> str:
    """A fitting emoji icon for a fact box, from its words."""
    rules = [
        (r"₹|રૂ|ફી|ભાવ|કિંમત|પગાર|price|fee|cost", "💰"), (r"દિવસ|તારીખ|date|day|મહિન|વર્ષ", "📅"),
        (r"વાગ્યા|સમય|કલાક|time|hour", "⏰"), (r"ધરપકડ|આરોપી|પોલીસ|arrest|police", "🚔"),
        (r"જિલ્લ|શહેર|ગામ|સ્થળ|place|city", "📍"), (r"વિદ્યાર્થી|પરીક્ષા|ધોરણ|exam|school", "🎓"),
        (r"વીજ|લાઈટ|power|electric", "⚡"), (r"ખેડૂત|પાક|farmer|crop", "🌾"), (r"હોસ્પિટલ|દર્દી|health", "🏥"),
        (r"સરકાર|યોજના|નિર્ણય|govt|scheme", "🏛️"), (r"ગેસ|પેટ્રોલ|ડીઝલ|CNG|fuel", "⛽"),
    ]
    for pattern, icon in rules:
        if re.search(pattern, text, re.I):
            return icon
    return "📌"


def big_number(story) -> str:
    """The most striking number in the story (for the bottom banner), or ''."""
    for text in [f["value"] for f in story.facts] + [story.headline, story.subheadline]:
        m = re.search(r"₹?\s?[\d૦-૯][\d૦-૯,.]*\s?(કરોડ|લાખ|%)?", text)
        if m:
            return m.group(0).strip()
    return ""


# Magazine design, modelled on Gemini-made Gujarati news posters: bright top, deep navy body, picture in a
# slanted frame on the right with a red callout, icon cards on the left, checklist panel, big-number banner.
MAG_CSS = """
  body { color: #fff; background:
    radial-gradient(circle at 80%% 8%%, rgba(255,255,255,.35), transparent 30%%),
    linear-gradient(180deg, %(top)s 0%%, %(top2)s 17%%, #0f1d4a 33%%, #0a1433 70%%, #050a1f 100%%); }
  .rays { position: absolute; inset: -400px -400px auto; height: 1100px;
    background: repeating-conic-gradient(from 0deg at 50%% 60%%, rgba(255,255,255,.10) 0deg 4deg, transparent 4deg 13deg);
    -webkit-mask: radial-gradient(circle at 50%% 60%%, #000, transparent 60%%); }
  .spark { position: absolute; border-radius: 50%%; }
  #main { position: absolute; inset: 0; padding: 40px 38px 34px; display: flex; flex-direction: column; gap: 18px; }
  .pill { align-self: center; background: #111a3a; border: 3px solid rgba(255,255,255,.25); border-radius: 40px;
    padding: 8px 34px; font-size: 44px; font-weight: 800; box-shadow: 0 10px 24px rgba(0,0,0,.4); }
  .h3d .back { color: #fff; -webkit-text-stroke: 20px #fff; text-shadow: 0 12px 0 #0b1340, 0 20px 36px rgba(0,0,0,.55); }
  .h3d .back .l3 { -webkit-text-stroke-color: #0b1340; color: #0b1340; }   /* dark outline keeps the light line readable */
  .h3d .front .l1 { background: linear-gradient(180deg, #7fd3ff, #1f6feb 60%%, #0b3fa8); -webkit-background-clip: text;
    background-clip: text; color: transparent; }
  .h3d .front .l2 { background: linear-gradient(180deg, #ff7a7a, #e00000 60%%, #8b0000); -webkit-background-clip: text;
    background-clip: text; color: transparent; }
  .h3d .front .l3 { background: linear-gradient(180deg, #ffffff, #c9f3ff 50%%, #5ad1ff); -webkit-background-clip: text;
    background-clip: text; color: transparent; filter: drop-shadow(0 0 18px rgba(90,209,255,.8)); }
  .mid { flex: 1; min-height: 0; position: relative; display: flex; gap: 16px; }
  .col { width: 52%%; display: flex; flex-direction: column; gap: 14px; z-index: 2; }
  .tag { align-self: flex-start; background: #0b1340; border: 3px solid #ffb703; border-radius: 30px; padding: 6px 20px;
    font-size: 34px; font-weight: 800; }
  .strip { background: linear-gradient(90deg, #c1121f, rgba(193,18,31,.0)); padding: 6px 14px; font-size: var(--sub);
    font-weight: 800; border-radius: 8px; }
  .card { display: flex; gap: 14px; align-items: center; background: linear-gradient(180deg, #ffffff, #e7ecf7);
    color: #0b1340; border-radius: 26px; padding: 12px 18px 12px 12px; box-shadow: 0 12px 26px rgba(0,0,0,.45);
    font-size: var(--pt); font-weight: 800; line-height: 1.25; }
  .card .ic { flex: none; width: 94px; height: 94px; border-radius: 50%%; display: flex; align-items: center;
    justify-content: center; font-size: 52px; background: radial-gradient(circle at 35%% 30%%, #3d7bff, #0b2d8a);
    box-shadow: inset 0 -6px 0 rgba(0,0,0,.25), 0 6px 14px rgba(0,0,0,.35); border: 4px solid #fff; color: #fff; }
  .card .ic.q { font-size: 34px; font-weight: 800; line-height: 1.05; text-align: center; }
  .card .v { color: #d90429; }
  .card .s { font-size: .82em; font-weight: 700; color: #26305c; }
  .photo { position: absolute; right: -38px; top: 0; bottom: 120px; width: 60%%; z-index: 1;
    clip-path: polygon(14%% 0, 100%% 0, 100%% 100%%, 0 100%%); border-radius: 0; overflow: hidden;
    box-shadow: 0 20px 40px rgba(0,0,0,.6); }
  .photo .img { position: absolute; inset: 0; background-size: cover; background-position: center top; }
  .photo .emoji { position: absolute; left: 55%%; top: 45%%; transform: translate(-50%%,-50%%); font-size: 260px; }
  .photo .symbolic { left: auto; right: 0; border-radius: 0 0 0 14px; }
  .callout { position: absolute; right: -38px; bottom: 40px; width: 50%%; z-index: 3; padding: 26px 30px 26px 70px;
    background: linear-gradient(135deg, #e00000, #8b0000); transform: skewY(-8deg); text-align: center;
    box-shadow: 0 16px 30px rgba(0,0,0,.5); border-left: 8px solid #ffd60a; }
  .callout span { display: inline-block; transform: skewY(8deg); font-size: 58px; font-weight: 800; line-height: 1.1;
    color: #fff; text-shadow: 0 4px 0 rgba(0,0,0,.35); }
  .arrows { position: absolute; left: -10px; top: 50%%; transform: translateY(-50%%) skewY(8deg); font-size: 62px;
    line-height: .9; color: #ffd60a; filter: drop-shadow(0 4px 4px rgba(0,0,0,.4)); }
  .checks { position: relative; display: flex; align-items: center; gap: 14px; }
  .checks .side { font-size: 120px; filter: drop-shadow(0 12px 18px rgba(0,0,0,.5)); flex: none; }
  .checks .panel { flex: 1; background: #fff; color: #10183a; border-radius: 26px; padding: 14px 22px;
    display: flex; flex-direction: column; gap: 8px; box-shadow: 0 14px 30px rgba(0,0,0,.5); }
  .pt { display: flex; gap: 12px; align-items: flex-start; font-size: var(--pt); font-weight: 700; line-height: 1.28; }
  .pt i { flex: none; width: 1.05em; height: 1.05em; margin-top: .14em; border-radius: 50%%; background: #d90429; color: #fff;
    font-style: normal; font-size: .8em; display: flex; align-items: center; justify-content: center; font-weight: 900; }
  .bottom { background: linear-gradient(180deg, #13245e, #0a1433); border: 4px solid #ffd60a; border-radius: 26px;
    padding: 14px 22px; box-shadow: 0 14px 30px rgba(0,0,0,.55); }
  .bottom .t { text-align: center; font-size: 38px; font-weight: 800; color: #ffd60a; margin-bottom: 6px; }
  .bottom .row { display: flex; align-items: center; gap: 18px; justify-content: center; }
  .bottom .bign { font-size: 120px; font-weight: 800; line-height: 1; color: #ffe14d;
    text-shadow: 0 6px 0 #a35b00, 0 0 30px rgba(255,214,10,.5); white-space: nowrap; }
  .bottom .q { font-size: 46px; font-weight: 800; line-height: 1.2; background: #fff; color: #0b1340; border-radius: 18px;
    padding: 10px 20px; }
  .footer { color: #dfe6ff; text-shadow: 0 2px 6px #000; }
"""

MAG_TOPS = [("#ffd000", "#ff9f1c"), ("#ffb703", "#fb8500"), ("#ffe14d", "#ffb703"), ("#7ae582", "#25a18e"),
            ("#ff8fa3", "#e5383b")]


def headline_3tone(headline: str) -> str:
    """Headline in three coloured parts (blue / red / glowing white) with a thick white outline."""
    words = headline.split()
    n = len(words)
    a, b = max(1, round(n * .35)), max(2, round(n * .7))
    parts = [" ".join(words[:a]), " ".join(words[a:b]), " ".join(words[b:])]
    inner = "<br>".join(f'<span class="l{i + 1}">{esc(p)}</span>' for i, p in enumerate(parts) if p)
    return f'<div class="h3d"><span class="back">{inner}</span><span class="front">{inner}</span></div>'


def mag_page(story, theme: dict, font: str, image_url: str | None, date: str, handle: str) -> str:
    import random
    top, top2 = random.choice(MAG_TOPS)
    picture = (f'<div class="img" style="background-image:url({image_url})"></div>{SYMBOLIC}' if image_url
               else f'<div class="emoji">{theme["scene"][0]}</div>')
    cards = ""
    if story.summary:
        cards += f'<div class="card fit"><div class="ic q">શું<br>થયું?</div><div class="s">{esc(story.summary)}</div></div>'
    cards += "".join(
        f'<div class="card"><div class="ic">{icon_for(f["label"] + " " + f["value"])}</div>'
        f'<div>{esc(f["label"])}: <span class="v">{esc(f["value"])}</span></div></div>' for f in story.facts[:2])
    callout = ""
    if story.stamp:
        callout = f'<div class="callout"><div class="arrows">➜<br>➜</div><span>{esc(story.stamp)}</span></div>'
    checks = ""
    if story.points:
        checks = ('<div class="checks"><div class="side">🚨</div><div class="panel fit">'
                  + "".join(f'<div class="pt"><i>✓</i><span>{esc(p)}</span></div>' for p in story.points[:3])
                  + '</div><div class="side">📄</div></div>')
    num = big_number(story)
    bottom = (f'<div class="bottom"><div class="t">{highlight_numbers(story.subheadline)}</div>'
              f'<div class="row">{f"<div class=bign>{esc(num)}</div>" if num else ""}'
              f'<div class="q">{esc(story.cta)}</div></div></div>')
    css = MAG_CSS % {"top": top, "top2": top2}
    return _head(font, css, theme["accent"]) + f"""
  <div class="rays"></div>{_sparks("#ffd60a", 25)}
  <div id="main">
    <div class="pill">{esc(theme["tag"].split(" ", 1)[0])} {esc(story.kicker)}</div>
    {headline_3tone(story.headline)}
    <div class="mid">
      <div class="col"><div class="tag">🚨 {esc(story.kicker)}</div>{cards}</div>
      <div class="photo">{picture}</div>{callout}
    </div>
    {checks}
    {bottom}
    <div class="footer"><span>સ્રોત: {esc(story.source_name)} • {date}</span><span>{esc(handle)}</span></div>
  </div></body></html>"""
