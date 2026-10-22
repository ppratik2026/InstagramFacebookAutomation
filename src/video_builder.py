"""Turn the news card image into a Reel (MP4) with a slow zoom and background music."""
import random
import subprocess
from pathlib import Path

from .config import ROOT

MUSIC_DIR = ROOT / "assets" / "music"


def _run(args: list[str]) -> None:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{result.stderr[-3000:]}")


def media_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def pick_music() -> Path | None:
    tracks = sorted(p for p in MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".aac"))
    return random.choice(tracks) if tracks else None


def build_video(image: Path, vcfg: dict, out_path: Path, music: Path | None = None) -> Path:
    seconds, fps = float(vcfg["seconds"]), int(vcfg["fps"])
    frames = int(seconds * fps)

    if vcfg.get("zoom", True):
        # upscale first so the zoom is smooth, then zoom from 1.0 to ~1.08 over the whole clip
        video_filter = (
            f"scale=2160:3840,zoompan=z='1+0.08*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:s=1080x1920:fps={fps},format=yuv420p"
        )
        args = ["ffmpeg", "-y", "-i", str(image)]
    else:
        video_filter = "scale=1080:1920,format=yuv420p"
        args = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(image)]

    if music:
        # start somewhere in the first part of the song so it doesn't always open with the intro
        start = 0.0
        length = media_duration(music)
        if length > seconds + 20:
            start = random.uniform(0, min(60.0, length - seconds - 5))
        args += ["-ss", f"{start:.2f}", "-i", str(music)]
        audio_filter = (
            f"[1:a]volume={vcfg['music_volume']},afade=t=in:d=0.5,"
            f"afade=t=out:st={seconds - 1.5:.2f}:d=1.5[a]"
        )
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio_filter = "[1:a]anull[a]"

    args += [
        "-filter_complex", f"[0:v]{video_filter}[v];{audio_filter}",
        "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-r", str(fps),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(out_path),
    ]
    _run(args)
    return out_path
