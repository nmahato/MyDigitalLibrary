"""Thumbnail generation + cache."""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from ..config import FFMPEG, THUMB_DIR
from . import imaging  # noqa: F401  (configures Pillow)

THUMB_SIZE = 512


def thumb_file(photo_id: int) -> Path:
    return THUMB_DIR / f"{photo_id}.webp"


def ensure_thumb(photo_id: int, src_path: str, media_type: str, force: bool = False) -> Path | None:
    dst = thumb_file(photo_id)
    if dst.exists() and not force:
        return dst
    try:
        if media_type == "video":
            _video_thumb(src_path, dst)
        else:
            _image_thumb(src_path, dst)
    except Exception:
        pass
    if not dst.exists():
        _placeholder(dst, Path(src_path).suffix.lstrip(".").upper() or "FILE")
    return dst if dst.exists() else None


def _placeholder(dst: Path, label: str):
    try:
        im = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), (32, 36, 44))
        d = ImageDraw.Draw(im)
        d.rectangle([8, 8, THUMB_SIZE - 8, THUMB_SIZE - 8], outline=(70, 76, 88), width=2)
        text = f"{label}\n(unreadable)"
        d.multiline_text((THUMB_SIZE / 2, THUMB_SIZE / 2), text, fill=(150, 156, 168),
                         anchor="mm", align="center", spacing=8)
        im.save(dst, "WEBP", quality=70)
    except Exception:
        pass


def _image_thumb(src: str, dst: Path):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        im.save(dst, "WEBP", quality=80, method=4)


def _video_thumb(src: str, dst: Path):
    base = [FFMPEG, "-y", "-loglevel", "error", "-threads", "1"]
    tail = ["-frames:v", "1", "-an", "-sn", "-vf", f"scale={THUMB_SIZE}:-2", str(dst)]
    subprocess.run(base + ["-ss", "1", "-i", src] + tail,
                   capture_output=True, timeout=60)
    if not dst.exists():  # very short clip: grab the first frame
        subprocess.run(base + ["-i", src] + tail, capture_output=True, timeout=60)
