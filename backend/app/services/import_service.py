"""Import media from an arbitrary folder into the library as YYYY / YYYY-MM-DD / Location."""
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

from ..config import library_path, load_settings
from ..repositories import photos as photo_repo
from . import exif, geocoding, indexer
from .hashing import sha256_file

PROGRESS = {
    "running": False, "phase": "idle", "total": 0, "done": 0,
    "imported": 0, "skipped_dupe": 0, "errors": 0, "current": "",
    "log": [], "dry_run": False, "finished_at": None,
}

_SAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _safe_name(s: str) -> str:
    s = _SAFE.sub("_", (s or "").strip()).strip(". ")
    return s[:60] or "Unknown"


def _target_for(src: Path, root: Path) -> Path:
    mtype = indexer.media_type(src.suffix)
    meta = (exif.extract_video(str(src)) if mtype == "video"
            else exif.extract_image(str(src)))

    taken = meta.get("taken_at") or exif.date_from_filename(src.name)
    try:
        dt = datetime.fromisoformat(taken) if taken else None
    except ValueError:
        dt = None
    if dt is None:
        dt = datetime.fromtimestamp(src.stat().st_mtime)

    location = None
    if meta.get("gps_lat") is not None:
        try:
            location = geocoding.label_for(meta["gps_lat"], meta["gps_lon"])
        except Exception:
            location = None

    return (root / f"{dt:%Y}" / f"{dt:%Y-%m-%d}"
            / _safe_name(location or "Unknown location") / src.name)


def _source_media(source: str) -> tuple[Path, list[Path]]:
    src_root = Path(source)
    files = [p for p in src_root.rglob("*")
             if p.is_file() and indexer.media_type(p.suffix)] if src_root.exists() else []
    return src_root, files


def plan(source: str, limit: int = 400) -> dict:
    src_root, files = _source_media(source)
    if not src_root.exists():
        return {"error": f"source not found: {source}"}

    root = library_path()
    known = photo_repo.known_shas()
    items, dupes = [], 0
    for p in sorted(files):
        try:
            sha = sha256_file(str(p))
        except OSError:
            continue
        if sha in known:
            dupes += 1
            continue
        if len(items) < limit:
            items.append({
                "source": str(p),
                "target": str(_target_for(p, root).relative_to(root)),
                "size_bytes": p.stat().st_size,
            })
    return {
        "total_media": len(files),
        "already_in_library": dupes,
        "to_import": len(files) - dupes,
        "preview": items,
        "mode": load_settings().get("import_mode", "copy"),
    }


def running() -> bool:
    return PROGRESS["running"]


def start(source: str, dry_run: bool = False) -> dict:
    if PROGRESS["running"]:
        return {"started": False, "reason": "already running"}
    threading.Thread(target=_run, args=(source, dry_run), daemon=True).start()
    return {"started": True}


def _run(source: str, dry_run: bool):
    src_root, files = _source_media(source)
    root = library_path()
    mode = load_settings().get("import_mode", "copy")
    PROGRESS.update(running=True, phase="importing", total=len(files), done=0,
                    imported=0, skipped_dupe=0, errors=0, current="", log=[],
                    dry_run=dry_run, finished_at=None)
    try:
        if not src_root.exists():
            PROGRESS["phase"] = f"source not found: {source}"
            return

        known = photo_repo.known_shas()
        for p in files:
            PROGRESS["done"] += 1
            PROGRESS["current"] = p.name
            try:
                sha = sha256_file(str(p))
                if sha in known:
                    PROGRESS["skipped_dupe"] += 1
                    continue

                dst = _dedupe_name(_target_for(p, root), sha)
                if dst is None:
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
                known.add(sha)
                indexer.index_file(dst, dst.stat(), None)
                PROGRESS["log"].append(f"{mode}: {p.name} -> {rel}")
                PROGRESS["imported"] += 1
            except Exception as e:  # noqa: BLE001
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
    i = 1
    while True:
        cand = dst.with_name(f"{dst.stem} ({i}){dst.suffix}")
        if not cand.exists():
            return cand
        i += 1
