"""Gujarat news -> image Reel -> Instagram.

    python main.py run                       # find news, make the reel, post it
    python main.py run --no-publish          # make the reel only, review output/ first
    python main.py run --category crime      # crime | good_news | government
    python main.py publish output/<dir>/reel.mp4 --caption-file output/<dir>/caption.txt
    python main.py prepare                   # semi-auto: news + Gemini prompt as a GitHub issue
    python main.py from-issue                # semi-auto: poster uploaded to the issue -> reel -> post
    python main.py check                     # verify the Instagram token
    python main.py refresh-token             # extend the token by 60 days
"""
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from src.config import ROOT, load_config, require_env


def post_reel(cfg: dict, video: Path, caption: str, ig=None) -> dict:
    """Publish the reel. Its cover is the frame 2.5 s before the end (the finished poster), never the first
    frame, which is the white flash of the intro."""
    import subprocess

    from src.hosting import video_urls
    from src.video_builder import media_duration

    at = max(0.0, media_duration(video) - 2.5)
    cover = video.with_name("cover.jpg")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
                    "-q:v", "2", str(cover)], check=True)
    try:
        sources = video_urls(video, cover)
    except Exception as e:   # hosting is best effort: the direct upload is still tried
        print(f"   Could not host the video: {e}")
        sources = []
    return (ig or instagram(cfg)).publish_reel(video, caption, cfg["instagram"]["share_to_feed"],
                                               sources=sources, thumb_offset_ms=int(at * 1000))


def instagram(cfg: dict):
    from src.publisher import Instagram
    return Instagram(require_env("IG_USER_ID"), require_env("IG_ACCESS_TOKEN"), cfg["instagram"]["api_version"])


def cmd_run(args, cfg):
    from src.backgrounds import get_background
    from src.card import render_card
    from src.history import add_entry, last_category, recent_titles
    from src.poster import make_poster
    from src.video_builder import build_video, pick_music, reel_seconds

    if cfg.get("provider") == "gemini":
        from src.news import find_story
        require_env("GEMINI_API_KEY")
    else:
        from src.free_news import find_story

    if not args.no_publish:
        ig = instagram(cfg)  # fail early if the Instagram secrets are missing

    work_dir = ROOT / "output" / datetime.now().strftime("%Y%m%d-%H%M%S")
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"1/4 Finding Gujarat news ({cfg.get('provider', 'free')})...")
    previous = recent_titles()
    if args.skip_titles and Path(args.skip_titles).exists():   # e.g. stories already shown in test previews
        previous += [t.strip() for t in Path(args.skip_titles).read_text(encoding="utf-8").splitlines() if t.strip()]
    from src.history import is_repeat
    story = None
    if getattr(args, "breaking", False):   # between the hourly posts: only a really big story, else nothing
        from src.free_news import find_breaking
        found = find_breaking(cfg, previous)
        if not found or is_repeat(found[0].title_en, recent_titles()):
            print("   No big breaking story right now.")
            raise SystemExit(3)
        order = []
        story, notes = found
    elif args.category:
        order = [args.category]
    else:   # categories in turn: the one after the last post's category first, the others as fallbacks
        names = list(cfg["content"]["categories"])
        last = last_category()
        first = (names.index(last) + 1) % len(names) if last in names else 0
        order = names[first:] + names[:first]
    for n, category in enumerate(order):
        print(f"   Category: {category}")
        for _ in range(3):   # the same story from another site is skipped and another one picked
            try:
                story, notes = find_story(cfg, previous, category)
            except RuntimeError as e:   # no fresh story in this category: take the next one
                print(f"   No story for {category} ({e}).")
                story = None
                break
            if not is_repeat(story.title_en, recent_titles()):
                break
            print(f"   Already posted a story like this ({story.title_en}); picking another one.")
            previous.append(re.search(r"^Headline: (.*)$", notes, re.M).group(1))
            story = None
        if story:
            break
    if not story:
        raise RuntimeError("No new story to post in any category.")
    caption = story.full_caption()
    (work_dir / "research.md").write_text(notes, encoding="utf-8")
    (work_dir / "story.json").write_text(json.dumps(story.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    (work_dir / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"   [{story.category}] {story.title_en}")
    print(f"   Source: {story.source_name} {story.source_url}")

    print("2/4 Designing the news poster...")
    card = None
    # Gemini poster whenever there is a key (needs billing on the key: the free tier has no image quota)
    # the whole AI poster can draw people, so it is only used when scene pictures are allowed
    if (os.environ.get("GEMINI_API_KEY") and cfg["card"].get("style", "ai_poster") == "ai_poster"
            and cfg["card"].get("picture", "cutout") != "cutout"):
        card = make_poster(story, cfg, work_dir / "card.png")
        if not card:
            print("   Gemini poster not available, trying the next option.")
    if not card and cfg.get("provider") != "gemini" and cfg["free"].get("ai_poster_models"):
        # the same prompt a person would paste into the Gemini app, sent to free image models
        from src.backgrounds import generate_free_poster
        from src.poster import _poster_prompt
        prompt = _poster_prompt(story, cfg["card"]["handle"])
        (work_dir / "poster_prompt.txt").write_text(prompt, encoding="utf-8")
        card = generate_free_poster(prompt, cfg["free"]["ai_poster_models"], work_dir / "card.png")
        if not card:
            print("   Free AI poster not available, using the template design.")
    intro_dir = None
    if not card:
        from src.backgrounds import generate_cutout
        from src.card import choose_design
        design = choose_design(story, cfg)
        background = cutout = None
        story.stamp = "" if not cfg["card"].get("stamps", False) else story.stamp
        if cfg["card"].get("picture", "cutout") == "cutout":
            # only the story's objects as a 3D cut-out: never a person (no AI faces, no real photos); without
            # a cut-out the design shows a big 3D icon
            story.person = ""
            design = "bulletin"
            cutout = generate_cutout(story.object_prompt, work_dir / "cutout.png")
        else:
            from src.people import person_photo
            photo = person_photo(story.person, work_dir / "person.jpg") if story.person else None
            if photo:   # a story about a public figure shows their real photo, never an AI-made face
                background, story.photo_credit = photo
                story.stamp = ""
            elif design == "bulletin" or story.person:   # the story's objects as a 3D cut-out (no people)
                cutout = generate_cutout(story.object_prompt, work_dir / "cutout.png")
                if story.person:
                    design = "bulletin"
            # an AI scene would put a made-up face on a real person's story: then only the cut-out or an icon
            if not cutout and not background and not story.person:
                background = get_background(story, cfg, work_dir)
        if cfg["video"].get("intro_animation", True):
            intro_dir = work_dir / "intro"
        card = render_card(story, cfg, work_dir / "card.png", background, intro_dir, design, cutout)
        card = _checked_card(story, cfg, card, background, intro_dir, design, cutout)

    print("3/4 Making the reel...")
    from src.designs import mood_of
    music = pick_music(mood_of(story))
    story.style["music"] = music.stem if music else ""
    print(f"   Music: {music.name if music else 'none (add mp3 files to assets/music/)'}")
    seconds = reel_seconds(mood_of(story), len(story.points))
    video = build_video(card, cfg["video"], work_dir / "reel.mp4", music, intro_dir, seconds)
    print(f"   Saved {video.relative_to(ROOT)}")

    if args.no_publish:
        print("Done (not published). Check the video, then run:")
        print(f"   python main.py publish {video.relative_to(ROOT)} --caption-file {(work_dir / 'caption.txt').relative_to(ROOT)}")
        return

    print("4/4 Publishing to Instagram...")
    result = post_reel(cfg, video, caption, ig)
    add_entry(story.title_en, result["media_id"], result.get("permalink"), story.category, story.style)
    print(f"Published: {result.get('permalink') or result['media_id']}")


def _checked_card(story, cfg, card: Path, background, intro_dir, design: str, cutout) -> Path:
    """Let the AI look at the poster; if it finds problems, make it again in other designs (without stickers)
    and keep the best one. Without an image-reading AI the poster is used as it is."""
    import shutil

    from src.card import render_card
    from src.qa import review

    result = review(card, story)
    if result is None:
        print("   Poster check not available; posting as made.")
        return card
    best_score, best, best_style = result[0], card, dict(story.style)
    print(f"   Poster check: {best_score}/10 {'; '.join(result[1])[:300]}")
    allowed = cfg["card"].get("designs", ["bulletin"])
    others = [d for d in ["bulletin", "split", "paper", "mag"] if d in allowed and d != design]
    # other designs first; with only one design allowed it is made again (another colour look and font)
    for n, other in enumerate((others + [design, design])[:2]):
        if best_score >= cfg["card"].get("min_check_score", 7):
            break
        if other != "bulletin" and cutout and not background:
            continue
        other_name = f"{other}{n}"
        sticker_share = cfg["card"].get("sticker_share", 0.3)
        cfg["card"]["sticker_share"] = 0   # a second try is kept plain
        attempt = render_card(story, cfg, card.with_name(f"card-{other_name}.png"), background, None, other, cutout)
        cfg["card"]["sticker_share"] = sticker_share
        again = review(attempt, story)
        if again is None:
            break
        print(f"   {other}: {again[0]}/10 {'; '.join(again[1])[:300]}")
        if again[0] > best_score:
            best_score, best, best_style = again[0], attempt, dict(story.style)
    if best != card:
        shutil.copy(best, card)
        if intro_dir:   # the intro animation belongs to the first design: the reel starts on the poster instead
            shutil.rmtree(intro_dir, ignore_errors=True)
    story.style = {**best_style, "check_score": best_score}   # the analytics learn from the look that was posted
    return card


def cmd_publish(args, cfg):
    from src.history import add_entry

    video = Path(args.video)
    caption = Path(args.caption_file).read_text(encoding="utf-8") if args.caption_file else (args.caption or "")
    result = post_reel(cfg, video, caption)
    story_file = video.parent / "story.json"
    title = json.loads(story_file.read_text(encoding="utf-8"))["title_en"] if story_file.exists() else video.stem
    add_entry(title, result["media_id"], result.get("permalink"))
    print(f"Published: {result.get('permalink') or result['media_id']}")


def cmd_prepare(args, cfg):
    """Find a story and write a GitHub issue (Gemini prompt + caption) for the semi-automatic flow."""
    from src.history import recent_titles
    from src.issue_flow import issue_body
    from src.poster import _poster_prompt

    if cfg.get("provider") == "gemini":
        from src.news import find_story
    else:
        from src.free_news import find_story

    work_dir = ROOT / "output" / datetime.now().strftime("%Y%m%d-%H%M%S")
    work_dir.mkdir(parents=True, exist_ok=True)
    previous = recent_titles()
    if args.skip_titles and Path(args.skip_titles).exists():   # stories already waiting in issues
        previous += [t.removeprefix("📰").strip() for t in Path(args.skip_titles).read_text(encoding="utf-8").splitlines() if t.strip()]
    story, notes = find_story(cfg, previous, args.category)
    prompt = _poster_prompt(story, cfg["card"]["handle"])
    (work_dir / "research.md").write_text(notes, encoding="utf-8")
    (work_dir / "story.json").write_text(json.dumps(story.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    (work_dir / "issue_title.txt").write_text(f"📰 {story.headline}", encoding="utf-8")
    from src.designs import mood_of
    (work_dir / "issue.md").write_text(issue_body(story, prompt, story.full_caption(), mood_of(story)), encoding="utf-8")
    print(f"Prepared: [{story.category}] {story.title_en}\n   {work_dir.relative_to(ROOT)}/issue.md")


def cmd_from_issue(args, cfg):
    """Turn the poster uploaded as an issue comment into a reel and post it (runs in GitHub Actions)."""
    import os

    from src.history import add_entry
    from src.issue_flow import caption_from, download, image_url_from, style_from, title_from
    from src.video_builder import build_video, pick_music, reel_seconds

    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    body, comment = event["issue"]["body"] or "", event["comment"]["body"] or ""
    url = image_url_from(comment)
    if not url:
        raise SystemExit("No image in the comment. Upload the poster image as a comment.")

    work_dir = ROOT / "output" / f"issue-{event['issue']['number']}"
    work_dir.mkdir(parents=True, exist_ok=True)
    poster = download(url, work_dir / "poster.png", os.environ.get("GITHUB_TOKEN", ""))
    caption = caption_from(body) or event["issue"]["title"]
    (work_dir / "caption.txt").write_text(caption, encoding="utf-8")
    mood, n_points = style_from(body)
    seconds = reel_seconds(mood, n_points)
    print(f"Mood: {mood or '-'} -> {seconds}s")
    video = build_video(poster, cfg["video"], work_dir / "reel.mp4", pick_music(mood), seconds=seconds)
    print(f"Reel: {video.relative_to(ROOT)}")
    if args.no_publish:
        return
    result = post_reel(cfg, video, caption)
    add_entry(title_from(body) or event["issue"]["title"], result["media_id"], result.get("permalink"))
    (ROOT / "output" / "result.txt").write_text(result.get("permalink") or result["media_id"], encoding="utf-8")
    print(f"Published: {result.get('permalink') or result['media_id']}")


def cmd_samples(args, cfg):
    """Many different posters in one go (no reels, nothing posted): a different story for each, walking
    through the designs, colour looks and fonts so no two look the same. Writes samples/NN.png and sheets."""
    from PIL import Image

    from src import designs
    from src.backgrounds import generate_cutout, get_background
    from src.bulletin import PALETTES
    from src.card import render_card
    from src.free_news import gather_items, write_card

    out_dir = ROOT / "samples"
    out_dir.mkdir(exist_ok=True)
    items = gather_items(cfg, [], list(cfg["content"]["categories"]), limit=200)
    # half bulletin (each colour look in turn), half the other designs in turn
    others = ["mag", "hero", "split", "paper", "classic"]
    looks = [("bulletin", pal) for pal in PALETTES] * 50
    plan = [looks[i // 2] if i % 2 == 0 else (others[(i // 2) % len(others)], "") for i in range(args.count)]
    made, seen, titles = [], [], []
    for item in items:
        if len(made) >= args.count:
            break
        words = set(item.title.split())
        if any(len(words & t) / max(1, len(words | t)) > 0.4 for t in titles):
            continue   # the same story from another site
        titles.append(words)
        n = len(made) + 1
        design, palette = plan[len(made)]
        print(f"\n[{n}/{args.count}] {design} {palette} - {item.title[:70]}")
        try:
            story, _ = write_card(cfg, item, item.category or "government", list(cfg["content"]["categories"]))
        except Exception as e:   # one bad story never stops the batch
            print(f"   skipped: {e}")
            continue
        # the same story again in other words (another site's take): compare the main words of the English title
        key = {w for w in re.findall(r"[a-z0-9]+", story.title_en.lower()) if len(w) > 3}
        if any(len(key & k) / max(1, min(len(key), len(k))) >= 0.5 for k in seen):
            print("   skipped: same story as an earlier sample")
            continue
        seen.append(key)
        work = out_dir / f"{n:02d}"
        work.mkdir(exist_ok=True)
        cfg["card"]["font"] = designs.FONTS[n % len(designs.FONTS)]
        os.environ["CARD_PALETTE"] = palette
        background = cutout = None
        if design == "bulletin":
            cutout = generate_cutout(story.object_prompt, work / "cutout.png")
        if not cutout:
            background = get_background(story, cfg, work)
        if design == "hero" and not background:
            design = "mag"
        try:
            card = render_card(story, cfg, work / "card.png", background, None, design, cutout)
        except Exception as e:
            print(f"   render failed: {e}")
            continue
        made.append(card)
        (work / "story.json").write_text(json.dumps(story.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    # contact sheets, 10 posters each, to look at them quickly
    for start in range(0, len(made), 10):
        sheet = Image.new("RGB", (5 * 432, 2 * 768), "white")
        for i, path in enumerate(made[start:start + 10]):
            sheet.paste(Image.open(path).convert("RGB").resize((432, 768)), ((i % 5) * 432, (i // 5) * 768))
        sheet.save(out_dir / f"sheet-{start // 10 + 1}.jpg", quality=88)
    print(f"\n{len(made)} samples in {out_dir.relative_to(ROOT)}/")


def cmd_scheduler(args, cfg):
    """Post one reel every hour from 10:00 to midnight IST, for `--hours` hours (GitHub Actions jobs stop
    at 6 hours; the workflow then starts the next scheduler run). Each post runs `main.py run` and saves
    the posted history to the repository, so a restarted scheduler never posts the same hour twice."""
    import subprocess
    import sys
    import time
    from datetime import timedelta

    from src.history import load_history
    from src.news import IST

    branch = os.environ.get("GITHUB_REF_NAME", "")
    stop_at = time.time() + args.hours * 3600

    def git(*a):
        return subprocess.run(["git", *a], capture_output=True, text=True)

    def sync():
        if branch:
            git("pull", "-q", "--rebase", "origin", branch)   # posts made by other runs

    def posts_ist() -> list[datetime]:
        return [datetime.fromisoformat(p["date"]).astimezone(IST) for p in load_history() if p.get("date")]

    def save(stats: bool):
        if not branch:
            return
        if stats:   # every few hours: fetch the reels' views and update the page report
            try:
                from src.analytics import update_stats
                update_stats(os.environ["IG_ACCESS_TOKEN"].strip(), cfg["instagram"]["api_version"])
            except Exception as e:   # the analytics never stop the posting
                print(f"   Stats update failed: {e}", flush=True)
        for name in ("data/history.json", "data/stats.json", "data/report.md"):
            if (ROOT / name).exists():
                git("add", name)
        git("-c", "user.name=github-actions[bot]",
            "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit", "-qm", "Update posted history and stats")
        for _ in range(3):
            if git("push", "-q", "origin", f"HEAD:{branch}").returncode == 0:
                break
            git("pull", "-q", "--rebase", "origin", branch)

    max_extra = cfg.get("schedule", {}).get("max_breaking_per_day", 6)
    while True:
        now = datetime.now(IST)
        if now.hour >= 10 or now.hour == 0:   # 10:00 ... 23:00 and midnight
            sync()
            posts = posts_ist()
            if not any(p.strftime("%Y%m%d%H") == now.strftime("%Y%m%d%H") for p in posts):
                print(f"\n=== {now:%d %b %H:%M} IST: hourly post ===", flush=True)
                if subprocess.run([sys.executable, "-u", "main.py", "run"]).returncode == 0:
                    save(stats=now.hour % 3 == 1)
            elif 15 <= now.minute <= 45 and (now - max(posts)).total_seconds() >= 20 * 60:
                # between the hourly posts: a really big breaking story goes out at once (a few a day at most)
                today = sum(1 for p in posts if p.date() == now.date())
                hours_so_far = (now.hour - 9) if now.hour >= 10 else 15
                if today - hours_so_far < max_extra:
                    print(f"\n=== {now:%d %b %H:%M} IST: breaking news check ===", flush=True)
                    if subprocess.run([sys.executable, "-u", "main.py", "run", "--breaking"]).returncode == 0:
                        save(stats=False)
        # wake at the next hour, or in 20 minutes for the breaking news check
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        wake = min(next_hour + timedelta(seconds=20), datetime.now(IST) + timedelta(minutes=20))
        wait = (wake - datetime.now(IST)).total_seconds()
        if time.time() + wait > stop_at:
            print("Time is up for this run; the next scheduler run takes over.", flush=True)
            return
        print(f"Next check at {wake:%H:%M} IST", flush=True)
        time.sleep(max(wait, 1))


def cmd_stats(args, cfg):
    """Fetch the reels' Instagram insights and write data/report.md."""
    from src.analytics import REPORT_FILE, update_stats
    stats = update_stats(require_env("IG_ACCESS_TOKEN"), cfg["instagram"]["api_version"])
    print(f"Insights for {len(stats)} reels; report: {REPORT_FILE.relative_to(ROOT)}")


def cmd_check(args, cfg):
    me = instagram(cfg).me()
    print(f"Token OK: @{me['username']} ({me['account_type']}), user_id={me['user_id']}")


def cmd_refresh(args, cfg):
    from src.publisher import refresh_token

    data = refresh_token(require_env("IG_ACCESS_TOKEN"))
    days = int(data.get("expires_in", 0)) // 86400
    # Written to a git-ignored file instead of printed, so the token never lands in logs.
    out = ROOT / ".new_token"
    out.write_text(data["access_token"], encoding="utf-8")
    print(f"Token refreshed, valid for ~{days} days. New token written to {out.name}; put it in .env / GitHub Secrets.")


def main():
    parser = argparse.ArgumentParser(description="Gujarat news image Reels -> Instagram")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="find news, make a reel and (by default) publish it")
    run.add_argument("--no-publish", action="store_true", help="only make the video")
    run.add_argument("--category", choices=["crime", "good_news", "government"], help="limit to one category")
    run.add_argument("--skip-titles", help="file with headlines to avoid (one per line)")
    run.add_argument("--breaking", action="store_true", help="post only if there is a really big breaking story")
    run.set_defaults(func=cmd_run)

    pub = sub.add_parser("publish", help="publish an existing video file")
    pub.add_argument("video")
    pub.add_argument("--caption")
    pub.add_argument("--caption-file")
    pub.set_defaults(func=cmd_publish)

    prep = sub.add_parser("prepare", help="find news and write a GitHub issue with a Gemini poster prompt")
    prep.add_argument("--category", choices=["crime", "good_news", "government"], help="limit to one category")
    prep.add_argument("--skip-titles", help="file with headlines to avoid (one per line), e.g. recent issue titles")
    prep.set_defaults(func=cmd_prepare)

    iss = sub.add_parser("from-issue", help="make and post the reel from a poster uploaded to an issue")
    iss.add_argument("--no-publish", action="store_true")
    iss.set_defaults(func=cmd_from_issue)

    smp = sub.add_parser("samples", help="many different posters from different stories (nothing is posted)")
    smp.add_argument("--count", type=int, default=50)
    smp.set_defaults(func=cmd_samples)

    sch = sub.add_parser("scheduler", help="post every hour from 10:00 to midnight IST (runs for --hours)")
    sch.add_argument("--hours", type=float, default=5.5)
    sch.set_defaults(func=cmd_scheduler)

    sub.add_parser("stats", help="fetch the reels' views and write data/report.md").set_defaults(func=cmd_stats)
    sub.add_parser("check", help="verify the Instagram token").set_defaults(func=cmd_check)
    sub.add_parser("refresh-token", help="extend the Instagram token by 60 days").set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    args.func(args, load_config())


if __name__ == "__main__":
    main()
