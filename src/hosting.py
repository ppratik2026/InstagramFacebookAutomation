"""Public links for the reel video. The Instagram API (Instagram Login) fetches the video from a URL, so in
GitHub Actions the file is pushed to the repository's "media" branch (only the latest video is kept) and
served from there. Needs a public repository and the workflow's contents: write permission."""
import os
import subprocess
from pathlib import Path

BRANCH = "media"


def _git(*args: str, stdin: str | None = None) -> str:
    return subprocess.run(["git", *args], input=stdin, check=True, capture_output=True, text=True).stdout.strip()


def video_urls(video: Path) -> list[str]:
    """Push the video to the media branch and return public URLs for it, best first. [] outside GitHub Actions."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        return []
    name = f"reel-{os.environ.get('GITHUB_RUN_ID', 'local')}.mp4"
    # one commit holding only this video, with no parent, so the branch never grows
    blob = _git("hash-object", "-w", str(video))
    tree = _git("mktree", stdin=f"100644 blob {blob}\t{name}\n")
    os.environ.setdefault("GIT_AUTHOR_NAME", "github-actions[bot]")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "41898282+github-actions[bot]@users.noreply.github.com")
    os.environ.setdefault("GIT_COMMITTER_NAME", os.environ["GIT_AUTHOR_NAME"])
    os.environ.setdefault("GIT_COMMITTER_EMAIL", os.environ["GIT_AUTHOR_EMAIL"])
    sha = _git("commit-tree", tree, "-m", f"Reel video for run {os.environ.get('GITHUB_RUN_NUMBER', '')}")
    _git("push", "-qf", "origin", f"{sha}:refs/heads/{BRANCH}")
    print(f"   Video hosted on the '{BRANCH}' branch ({sha[:7]})")
    return [
        f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/{name}",          # served as video/mp4
        f"https://raw.githubusercontent.com/{repo}/{sha}/{name}",
    ]
