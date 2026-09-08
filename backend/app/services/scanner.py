"""Walk the library, extract metadata + hashes, keep the DB in sync."""
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ..config import IMAGE_EXTS, VIDEO_EXTS, library_path
from ..database import get_conn
from . import exif, geocode
from .hashing import phash, sha256_file
from .thumbnails import ensure_thumb

PROGRESS = {
    "running": False, "phase": "idle", "total": 0, "done": 0,
    "added": 0, "updated": 0, "removed": 0, "errors": 0,
    "current": "", "started_at": None, "finished_at": None,
}
_lock = threading.Lock()


def _media_type(ext: str) -> str | None:
    ext = ext.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def is_running() -> bool:
    return PROGRESS["running"]


def start_scan(full: bool = False):
    if PROGRESS["running"]:
        return
    t = threading.Thread(target=_scan, args=(full,), daemon=True)
    t.start()


def _scan(full: bool):
    root = library_path()
    with _lock:
        PROGRESS.update(running=True, phase="listing", total=0, done=0, added=0,
                        updated=0, removed=0, errors=0, current="",
                        started_at=datetime.now().isoformat(), finished_at=None)
    try:
        if not root.exists():
            PROGRESS["phase"] = f"library not found: {root}"
            return

        files = [p for p in root.rglob("*")
                 if p.is_file() and _media_type(p.suffix)]
        PROGRESS.update(total=len(files), phase="indexing")

        with get_conn() as conn:
            known = {r["path"]: r for r in conn.execute(
                "SELECT id, path, size_bytes, fs_modified, phash, sha256 FROM photos")}

        seen: set[str] = set()
        for p in files:
            PROGRESS["done"] += 1
            PROGRESS["current"] = p.name
            path = str(p)
            seen.add(path)
            try:
                st = p.stat()
                fs_modified = datetime.fromtimestamp(st.st_mtime).isoformat()
                row = known.get(path)
                if row and not full and row["fs_modified"] == fs_modified \
                        and row["size_bytes"] == st.st_size and row["phash"]:
                    continue
                _index_file(p, st, fs_modified, row)
                if row:
                    PROGRESS["updated"] += 1
                else:
                    PROGRESS["added"] += 1
            except Exception:
                PROGRESS["errors"] += 1

        # mark rows whose files disappeared
        gone = [r["id"] for path, r in known.items() if path not in seen]
        if gone:
            with get_conn() as conn:
                conn.executemany("DELETE FROM photos WHERE id=?", [(i,) for i in gone])
            PROGRESS["removed"] = len(gone)

        PROGRESS["phase"] = "done"
    finally:
        PROGRESS["running"] = False
        PROGRESS["finished_at"] = datetime.now().isoformat()


def _index_file(p: Path, st, fs_modified: str, existing):
    root = library_path()
    ext = p.suffix.lower()
    mtype = _media_type(ext)
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
            location = geocode.label_for(meta["gps_lat"], meta["gps_lon"])
        except Exception:
            location = None

    sha = sha256_file(str(p))
    ph = None
    if mtype == "image":
        try:
            with Image.open(str(p)) as im:
                ph = phash(im)
        except Exception:
            ph = None

    fields = {
        "path": str(p),
        "rel_path": str(p.relative_to(root)) if str(p).startswith(str(root)) else p.name,
        "filename": p.name,
        "ext": ext.lstrip("."),
        "media_type": mtype,
        "size_bytes": st.st_size,
        "width": meta.get("width"),
        "height": meta.get("height"),
        "duration_sec": meta.get("duration_sec"),
        "taken_at": taken_at,
        "date_source": date_source,
        "fs_modified": fs_modified,
        "camera_make": meta.get("camera_make"),
        "camera_model": meta.get("camera_model"),
        "gps_lat": meta.get("gps_lat"),
        "gps_lon": meta.get("gps_lon"),
        "location": location,
        "orientation": meta.get("orientation", 1),
        "sha256": sha,
        "phash": ph,
        "indexed_at": datetime.now().isoformat(),
    }

    with get_conn() as conn:
        if existing:
            cols = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE photos SET {cols}, faces_done=0 WHERE id=?",
                         (*fields.values(), existing["id"]))
            pid = existing["id"]
        else:
            cols = ", ".join(fields)
            ph_marks = ", ".join("?" for _ in fields)
            cur = conn.execute(f"INSERT INTO photos ({cols}) VALUES ({ph_marks})",
                               tuple(fields.values()))
            pid = cur.lastrowid

    ensure_thumb(pid, str(p), mtype, force=bool(existing))
