import json
import math
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4
from PIL import Image
from .models import Asset

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".mp4",
    ".mov",
    ".m4v",
    ".webm",
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
}
MAX_UPLOAD = 512 * 1024 * 1024


def run(args: list[str], timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, check=True, timeout=timeout)


def probe(path: Path) -> dict:
    if not FFPROBE:
        raise ValueError("ffprobe belum terpasang.")
    return json.loads(
        run(
            [
                FFPROBE,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        ).stdout
    )


def inspect_media(path: Path, name: str) -> Asset:
    ext = path.suffix.lower()
    if ext not in EXTENSIONS:
        raise ValueError("Format media belum didukung.")
    aid = uuid4().hex
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            width, height = im.size
        return Asset(
            id=aid,
            name=name[:240],
            file=aid + ext,
            kind="image",
            width=width,
            height=height,
        )
    info = probe(path)
    streams = info.get("streams", [])
    visual = next(
        (
            s
            for s in streams
            if s["codec_type"] == "video"
            and not s.get("disposition", {}).get("attached_pic")
        ),
        None,
    )
    sound = next((s for s in streams if s["codec_type"] == "audio"), None)
    if not visual and not sound:
        raise ValueError("File tidak memiliki stream media yang dapat dipakai.")
    duration = float(info["format"].get("duration", 0))
    if not math.isfinite(duration) or duration <= 0 or duration > 3600:
        raise ValueError("Durasi media harus antara 0 dan 3600 detik.")
    return Asset(
        id=aid,
        name=name[:240],
        file=aid + ext,
        kind="video" if visual else "audio",
        frames=math.ceil(duration * 30),
        width=visual.get("width", 0) if visual else 0,
        height=visual.get("height", 0) if visual else 0,
        has_audio=bool(sound),
    )


def make_peaks(path: Path) -> list[float]:
    import array

    if not FFMPEG:
        return []
    pcm = run(
        [
            FFMPEG,
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(path),
            "-t",
            "180",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "1000",
            "-f",
            "s16le",
            "pipe:1",
        ]
    ).stdout
    samples = array.array("h", pcm)
    chunk = max(1, len(samples) // 80)
    return [
        round(max(abs(x) for x in samples[i : i + chunk]) / 32768, 3)
        for i in range(0, len(samples), chunk)
    ][:80]
