"""Public links for the reel video. The Instagram API (Instagram Login) fetches the video from a URL, so in
GitHub Actions the file is pushed to the repository's "media" branch (only the latest video is kept) and
served from there. Needs a public repository and the workflow's contents: write permission."""
import os
import subprocess
from pathlib import Path

BRANCH = "media"


def _git(*args: str, stdin: str | None = None) -> str:
    return subprocess.run(["git", *args], input=stdin, check=True, capture_output=True, text=True).stdout.strip()


def video_urls(video: Path, cover: Path | None = None) -> list[dict]:
    """Push the video (and its cover image) to the media branch; return Instagram sources for it, best host
    first: [{"video_url": ..., "cover_url": ...}]. [] outside GitHub Actions."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return []
    run = os.environ.get("GITHUB_RUN_ID", "local")
    files = {f"reel-{run}.mp4": video}
    if cover:
        files[f"cover-{run}.jpg"] = cover
    # one commit holding only these files, with no parent, so the branch never grows
    entries = "".join(f"100644 blob {_git('hash-object', '-w', str(path))}\t{name}\n" for name, path in sorted(files.items()))
    tree = _git("mktree", stdin=entries)
    os.environ.setdefault("GIT_AUTHOR_NAME", "github-actions[bot]")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "41898282+github-actions[bot]@users.noreply.github.com")
    os.environ.setdefault("GIT_COMMITTER_NAME", os.environ["GIT_AUTHOR_NAME"])
    os.environ.setdefault("GIT_COMMITTER_EMAIL", os.environ["GIT_AUTHOR_EMAIL"])
    sha = _git("commit-tree", tree, "-m", f"Reel video for run {os.environ.get('GITHUB_RUN_NUMBER', '')}")
    _git("push", "-qf", "origin", f"{sha}:refs/heads/{BRANCH}")
    print(f"   Video hosted on the '{BRANCH}' branch ({sha[:7]})")
    sources = []
    for base in (f"https://cdn.jsdelivr.net/gh/{repo}@{sha}", f"https://raw.githubusercontent.com/{repo}/{sha}"):
        source = {"video_url": f"{base}/reel-{run}.mp4"}   # jsDelivr serves it as video/mp4
        if cover:
            source["cover_url"] = f"{base}/cover-{run}.jpg"
        sources.append(source)
    return sources
