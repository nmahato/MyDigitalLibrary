"""Import media from an arbitrary folder into the library as YYYY / YYYY-MM-DD / Location."""
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from ..config import IMAGE_EXTS, VIDEO_EXTS, library_path, load_settings
from ..database import get_conn
from . import exif, geocode
from .hashing import sha256_file
from .scanner import _index_file  # reuse indexing

PROGRESS = {
    "running": False, "phase": "idle", "total": 0, "done": 0,
    "imported": 0, "skipped_dupe": 0, "errors": 0, "current": "",
    "log": [], "dry_run": False, "finished_at": None,
}

_SAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_name(s: str) -> str:
    s = _SAFE.sub("_", (s or "").strip()).strip(". ")
    return s[:60] or "Unknown"


def _media_type(ext):
    ext = ext.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def _target_for(src: Path, root: Path) -> tuple[Path, dict]:
    ext = src.suffix.lower()
    mtype = _media_type(ext)
    meta = exif.extract_video(str(src)) if mtype == "video" else exif.extract_image(str(src))

    taken = meta.get("taken_at") or exif.date_from_filename(src.name)
    if taken:
        try:
            dt = datetime.fromisoformat(taken)
        except ValueError:
            dt = datetime.fromtimestamp(src.stat().st_mtime)
    else:
        dt = datetime.fromtimestamp(src.stat().st_mtime)

    location = None
    if meta.get("gps_lat") is not None:
        try:
            location = geocode.label_for(meta["gps_lat"], meta["gps_lon"])
        except Exception:
            location = None

    folder = root / f"{dt:%Y}" / f"{dt:%Y-%m-%d}" / _safe_name(location or "Unknown location")
    return folder / src.name, meta


def plan(source: str, limit: int = 400) -> dict:
    src_root = Path(source)
    root = library_path()
    if not src_root.exists():
        return {"error": f"source not found: {source}"}

    with get_conn() as conn:
        known_sha = {r["sha256"] for r in conn.execute(
            "SELECT sha256 FROM photos WHERE sha256 IS NOT NULL")}

    items, dupes, total = [], 0, 0
    for p in sorted(src_root.rglob("*")):
        if not p.is_file() or not _media_type(p.suffix):
            continue
        total += 1
        try:
            sha = sha256_file(str(p))
        except OSError:
            continue
        if sha in known_sha:
            dupes += 1
            continue
        if len(items) < limit:
            dst, _ = _target_for(p, root)
            items.append({
                "source": str(p),
                "target": str(dst.relative_to(root)),
                "size_bytes": p.stat().st_size,
            })
    return {
        "total_media": total,
        "already_in_library": dupes,
        "to_import": total - dupes,
        "preview": items,
        "mode": load_settings().get("import_mode", "copy"),
    }


def is_running():
    return PROGRESS["running"]


def start_import(source: str, dry_run: bool = False):
    if PROGRESS["running"]:
        return
    threading.Thread(target=_run, args=(source, dry_run), daemon=True).start()


def _run(source: str, dry_run: bool):
    src_root = Path(source)
    root = library_path()
    mode = load_settings().get("import_mode", "copy")
    PROGRESS.update(running=True, phase="scanning source", total=0, done=0,
                    imported=0, skipped_dupe=0, errors=0, current="", log=[],
                    dry_run=dry_run, finished_at=None)
    try:
        if not src_root.exists():
            PROGRESS["phase"] = f"source not found: {source}"
            return

        with get_conn() as conn:
            known_sha = {r["sha256"] for r in conn.execute(
                "SELECT sha256 FROM photos WHERE sha256 IS NOT NULL")}

        files = [p for p in src_root.rglob("*")
                 if p.is_file() and _media_type(p.suffix)]
        PROGRESS.update(total=len(files), phase="importing")

        for p in files:
            PROGRESS["done"] += 1
            PROGRESS["current"] = p.name
            try:
                sha = sha256_file(str(p))
                if sha in known_sha:
                    PROGRESS["skipped_dupe"] += 1
                    continue

                dst, _ = _target_for(p, root)
                dst = _dedupe_name(dst, sha)
                if dst is None:  # identical file already at destination
                    PROGRESS["skipped_dupe"] += 1
                    continue

                rel = dst.relative_to(root)
                if dry_run:
                    PROGRESS["log"].append(f"would {mode}: {p.name} -> {rel}")
                    PROGRESS["imported"] += 1
                    continue

                dst.parent.mkdir(parents=True, exist_ok=True)
                if mode == "move":
                    shutil.move(str(p), str(dst))
                else:
                    shutil.copy2(str(p), str(dst))
                known_sha.add(sha)

                st = dst.stat()
                _index_file(dst, st, datetime.fromtimestamp(st.st_mtime).isoformat(), None)
                PROGRESS["log"].append(f"{mode}: {p.name} -> {rel}")
                PROGRESS["imported"] += 1
            except Exception as e:
                PROGRESS["errors"] += 1
                PROGRESS["log"].append(f"ERROR {p.name}: {e}")

        PROGRESS["log"] = PROGRESS["log"][-500:]
        PROGRESS["phase"] = "done"
    finally:
        PROGRESS["running"] = False
        PROGRESS["finished_at"] = datetime.now().isoformat()


def _dedupe_name(dst: Path, sha: str) -> Path | None:
    if not dst.exists():
        return dst
    try:
        if sha256_file(str(dst)) == sha:
            return None
    except OSError:
        pass
    stem, suffix = dst.stem, dst.suffix
    i = 1
    while True:
        cand = dst.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand
        i += 1
