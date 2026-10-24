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


# How the picture moves, by news mood: (motion, seconds)
MOOD_STYLE = {
    "breaking": ("punch", 12),   # white flash and a fast punch-in, then a slow push
    "money": ("pulse", 14),      # gentle heartbeat zoom
    "info": ("pan", 18),         # slow pan from top to bottom so people can read
    "happy": ("reveal", 12),     # starts close, zooms out to show the whole poster
}


def style_for(mood: str, n_points: int = 0) -> tuple[str, float]:
    """Motion and length for a story: longer when there is more to read."""
    motion, seconds = MOOD_STYLE.get(mood, ("zoom", 15))
    return motion, seconds + (3 if n_points > 4 else 0)


def _motion_filter(motion: str, frames: int, fps: int) -> str:
    """zoompan expression for a motion; 'on' is the output frame number."""
    center = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    z, xy = {
        "punch": (f"if(lt(on,{fps // 2}),1.3-0.3*on/{fps // 2},1+0.04*(on-{fps // 2})/{frames})", center),
        "pulse": (f"1.03+0.025*sin(2*PI*on/{fps})", center),
        "pan": ("1.12", f"x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{frames}'"),
        "reveal": (f"1.2-0.2*on/{frames}", center),
    }.get(motion, (f"1+0.04*on/{frames}", center))
    return f"zoompan=z='{z}':{xy}:d={frames}:s=1080x1920:fps={fps}"


def build_video(image: Path, vcfg: dict, out_path: Path, music: Path | None = None,
                intro_dir: Path | None = None, motion: str = "zoom", seconds: float | None = None) -> Path:
    """Reel from the card image; with intro_dir, the animated intro frames play first."""
    seconds, fps = float(seconds or vcfg["seconds"]), int(vcfg["fps"])
    intro_frames = sorted(intro_dir.glob("f*.jpg")) if intro_dir else []
    intro_seconds = len(intro_frames) / fps
    frames = int((seconds - intro_seconds) * fps)

    if vcfg.get("zoom", True):
        # upscale first so the motion is smooth, then move the picture (gentle, so edge text stays in frame)
        video_filter = (
            "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
            f"{_motion_filter(motion, frames, fps)}"
        )
        if motion == "punch" and not intro_frames:
            video_filter += ",fade=t=in:st=0:d=0.35:color=white"
        video_filter += ",format=yuv420p"   # last, so every player (and Instagram) accepts the video
        args = ["ffmpeg", "-y", "-i", str(image)]
    else:
        video_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p"
        args = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(fps), "-i", str(image)]

    video_inputs = 1
    if intro_frames:
        # intro frames first, then the zoom on the finished card, joined into one stream
        args += ["-framerate", str(fps), "-i", str(intro_dir / "f%04d.jpg")]
        video_inputs = 2
        video_filter = f"{video_filter}[z];[1:v]scale=1080:1920,format=yuv420p,setsar=1[i];[i][z]concat=n=2:v=1:a=0"
    audio_in = video_inputs

    if music:
        # start somewhere in the first part of the song so it doesn't always open with the intro
        start = 0.0
        length = media_duration(music)
        if length > seconds + 20:
            start = random.uniform(0, min(60.0, length - seconds - 5))
        args += ["-ss", f"{start:.2f}", "-i", str(music)]
        audio_filter = (
            f"[{audio_in}:a]volume={vcfg['music_volume']},afade=t=in:d=0.5,"
            f"afade=t=out:st={seconds - 1.5:.2f}:d=1.5[a]"
        )
    else:
        args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio_filter = f"[{audio_in}:a]anull[a]"

    args += [
        "-filter_complex", f"[0:v]{video_filter},setsar=1[v];{audio_filter}",
        "-map", "[v]", "-map", "[a]", "-t", f"{seconds:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-r", str(fps),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", str(out_path),
    ]
    _run(args)
    return out_path
