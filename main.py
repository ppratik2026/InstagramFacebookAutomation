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
from datetime import datetime
from pathlib import Path

from src.config import ROOT, load_config, require_env


def instagram(cfg: dict):
    from src.publisher import Instagram
    return Instagram(require_env("IG_USER_ID"), require_env("IG_ACCESS_TOKEN"), cfg["instagram"]["api_version"])


def cmd_run(args, cfg):
    from src.backgrounds import get_background
    from src.card import render_card
    from src.history import add_entry, recent_titles
    from src.poster import make_poster
    from src.video_builder import build_video, pick_music, style_for

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
    story, notes = find_story(cfg, previous, args.category)
    caption = story.full_caption()
    (work_dir / "research.md").write_text(notes, encoding="utf-8")
    (work_dir / "story.json").write_text(json.dumps(story.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
    (work_dir / "caption.txt").write_text(caption, encoding="utf-8")
    print(f"   [{story.category}] {story.title_en}")
    print(f"   Source: {story.source_name} {story.source_url}")

    print("2/4 Designing the news poster...")
    card = None
    # Gemini poster whenever there is a key (needs billing on the key: the free tier has no image quota)
    if os.environ.get("GEMINI_API_KEY") and cfg["card"].get("style", "ai_poster") == "ai_poster":
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
        background = get_background(story, cfg, work_dir)
        if cfg["video"].get("intro_animation", True):
            intro_dir = work_dir / "intro"
        card = render_card(story, cfg, work_dir / "card.png", background, intro_dir)

    print("3/4 Making the reel...")
    music = pick_music()
    print(f"   Music: {music.name if music else 'none (add mp3 files to assets/music/)'}")
    from src.designs import mood_of
    motion, seconds = style_for(mood_of(story), len(story.points))
    video = build_video(card, cfg["video"], work_dir / "reel.mp4", music, intro_dir, motion, seconds)
    print(f"   Saved {video.relative_to(ROOT)}")

    if args.no_publish:
        print("Done (not published). Check the video, then run:")
        print(f"   python main.py publish {video.relative_to(ROOT)} --caption-file {(work_dir / 'caption.txt').relative_to(ROOT)}")
        return

    print("4/4 Publishing to Instagram...")
    result = ig.publish_reel(video, caption, cfg["instagram"]["share_to_feed"])
    add_entry(story.title_en, result["media_id"], result.get("permalink"))
    print(f"Published: {result.get('permalink') or result['media_id']}")


def cmd_publish(args, cfg):
    from src.history import add_entry

    video = Path(args.video)
    caption = Path(args.caption_file).read_text(encoding="utf-8") if args.caption_file else (args.caption or "")
    result = instagram(cfg).publish_reel(video, caption, cfg["instagram"]["share_to_feed"])
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
    from src.video_builder import build_video, pick_music, style_for

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
    motion, seconds = style_for(mood, n_points)
    print(f"Mood: {mood or '-'} -> motion: {motion}, {seconds}s")
    video = build_video(poster, cfg["video"], work_dir / "reel.mp4", pick_music(), motion=motion, seconds=seconds)
    print(f"Reel: {video.relative_to(ROOT)}")
    if args.no_publish:
        return
    result = instagram(cfg).publish_reel(video, caption, cfg["instagram"]["share_to_feed"])
    add_entry(title_from(body) or event["issue"]["title"], result["media_id"], result.get("permalink"))
    (ROOT / "output" / "result.txt").write_text(result.get("permalink") or result["media_id"], encoding="utf-8")
    print(f"Published: {result.get('permalink') or result['media_id']}")


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

    sub.add_parser("check", help="verify the Instagram token").set_defaults(func=cmd_check)
    sub.add_parser("refresh-token", help="extend the Instagram token by 60 days").set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    args.func(args, load_config())


if __name__ == "__main__":
    main()
