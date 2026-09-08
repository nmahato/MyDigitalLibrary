"""Thumbnail generation + cache."""
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from ..config import THUMB_DIR
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
        return None
    return dst if dst.exists() else None


def _image_thumb(src: str, dst: Path):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        im.save(dst, "WEBP", quality=80, method=4)


def _video_thumb(src: str, dst: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", src,
         "-frames:v", "1", "-vf", f"scale={THUMB_SIZE}:-2", str(dst)],
        capture_output=True, timeout=60,
    )
    if not dst.exists():  # very short clip: grab the first frame
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
             "-frames:v", "1", "-vf", f"scale={THUMB_SIZE}:-2", str(dst)],
            capture_output=True, timeout=60,
        )
