import json
import os
import shutil
from pathlib import Path

APP_DIR = Path(os.environ.get("IMAGEVIEWER_DATA", str(Path.home() / ".imageviewer")))
APP_DIR.mkdir(parents=True, exist_ok=True)

# ffmpeg / ffprobe: honour explicit paths (IIS app-pool identities often lack a
# useful PATH), else fall back to whatever is on PATH, else the bare name.
FFMPEG = os.environ.get("FFMPEG_BINARY") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.environ.get("FFPROBE_BINARY") or shutil.which("ffprobe") or "ffprobe"

DB_PATH = APP_DIR / "library.db"
THUMB_DIR = APP_DIR / "thumbnails"
THUMB_DIR.mkdir(exist_ok=True)

_SETTINGS_PATH = APP_DIR / "settings.json"

DEFAULT_LIBRARY = os.environ.get("PHOTO_LIBRARY", r"D:\PhotoLibrary")

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
    ".webp", ".heic", ".heif", ".avif",
}
VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".3gp",
    ".webm", ".mpg", ".mpeg", ".mts",
}
ALL_EXTS = IMAGE_EXTS | VIDEO_EXTS

_DEFAULT_WORKERS = min(8, (os.cpu_count() or 4) * 2)

_DEFAULTS = {
    "library_path": DEFAULT_LIBRARY,
    "import_mode": "copy",              # copy | move
    "near_duplicate_threshold": 8,      # max hamming distance for perceptual hash
    "geocode": "offline",              # offline | off | nominatim
    "nominatim_email": "",
    "scan_workers": _DEFAULT_WORKERS,   # parallel workers for library scan / import
}


def load_settings() -> dict:
    data = dict(_DEFAULTS)
    if _SETTINGS_PATH.exists():
        try:
            data.update(json.loads(_SETTINGS_PATH.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            pass
    return data


def save_settings(patch: dict) -> dict:
    data = load_settings()
    for k, v in patch.items():
        if k in _DEFAULTS:
            data[k] = v
    _SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def library_path() -> Path:
    return Path(load_settings()["library_path"])
