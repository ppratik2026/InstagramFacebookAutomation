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
  {picture}<div class="shade"></div>{_sparks(theme["bokeh"])}<div class="frame"></div>{extra}
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
