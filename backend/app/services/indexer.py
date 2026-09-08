"""Filesystem walker: turns media files into `photos` rows + thumbnails.

The scan loop and its progress state live in `library_service`; this module is the
per-file work and is also reused by the importer.
"""
from datetime import datetime
from pathlib import Path

from PIL import Image

from ..config import IMAGE_EXTS, VIDEO_EXTS, library_path
from ..repositories import photos as photo_repo
from . import exif, geocoding, imaging  # noqa: F401
from .hashing import phash, sha256_file
from .thumbnails import ensure_thumb


def media_type(ext: str) -> str | None:
    ext = ext.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def list_media(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and media_type(p.suffix)]


def build_fields(p: Path, st) -> tuple[dict, str]:
    """Extract every column value for a media file. Returns (fields, media_type)."""
    root = library_path()
    ext = p.suffix.lower()
    mtype = media_type(ext)
    meta = exif.extract_video(str(p)) if mtype == "video" else exif.extract_image(str(p))

    taken_at = meta.get("taken_at")
    date_source = "exif"
    if not taken_at:
        taken_at = exif.date_from_filename(p.name)
        date_source = "filename" if taken_at else None
    if not taken_at:
        taken_at = datetime.fromtimestamp(st.st_mtime).isoformat()
        date_source = "mtime"

    location = None
    if meta.get("gps_lat") is not None:
        try:
            location = geocoding.label_for(meta["gps_lat"], meta["gps_lon"])
        except Exception:
            location = None

    ph = None
    if mtype == "image":
        try:
            with Image.open(str(p)) as im:
                ph = phash(im)
        except Exception:
            ph = None

    try:
        rel = str(p.relative_to(root))
    except ValueError:
        rel = p.name

    fields = {
        "path": str(p),
        "rel_path": rel,
        "filename": p.name,
        "ext": ext.lstrip("."),
        "media_type": mtype,
        "size_bytes": st.st_size,
        "width": meta.get("width"),
        "height": meta.get("height"),
        "duration_sec": meta.get("duration_sec"),
        "taken_at": taken_at,
        "date_source": date_source,
        "fs_modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
        "camera_make": meta.get("camera_make"),
        "camera_model": meta.get("camera_model"),
        "gps_lat": meta.get("gps_lat"),
        "gps_lon": meta.get("gps_lon"),
        "location": location,
        "orientation": meta.get("orientation", 1),
        "sha256": sha256_file(str(p)),
        "phash": ph,
        "indexed_at": datetime.now().isoformat(),
    }
    return fields, mtype


def index_file(p: Path, st, existing_id: int | None = None) -> int:
    fields, mtype = build_fields(p, st)
    pid = photo_repo.upsert(fields, existing_id)
    ensure_thumb(pid, str(p), mtype, force=bool(existing_id))
    return pid
