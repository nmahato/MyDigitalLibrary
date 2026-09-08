"""Library-level operations: indexing scan, status, settings."""
import threading
from datetime import datetime
from pathlib import Path

from ..config import library_path, load_settings, save_settings
from ..repositories import photos as photo_repo
from . import indexer

SCAN = {
    "running": False, "phase": "idle", "total": 0, "done": 0,
    "added": 0, "updated": 0, "removed": 0, "errors": 0,
    "current": "", "started_at": None, "finished_at": None,
}
_lock = threading.Lock()


def scan_running() -> bool:
    return SCAN["running"]


def start_scan(full: bool = False) -> dict:
    if SCAN["running"]:
        return {"started": False, "reason": "already running"}
    threading.Thread(target=_scan, args=(full,), daemon=True).start()
    return {"started": True}


def _scan(full: bool):
    root = library_path()
    with _lock:
        SCAN.update(running=True, phase="listing", total=0, done=0, added=0,
                    updated=0, removed=0, errors=0, current="",
                    started_at=datetime.now().isoformat(), finished_at=None)
    try:
        if not root.exists():
            SCAN["phase"] = f"library not found: {root}"
            return

        files = indexer.list_media(root)
        SCAN.update(total=len(files), phase="indexing")
        known = photo_repo.known_index()

        seen: set[str] = set()
        for p in files:
            SCAN["done"] += 1
            SCAN["current"] = p.name
            path = str(p)
            seen.add(path)
            try:
                st = p.stat()
                fs_modified = datetime.fromtimestamp(st.st_mtime).isoformat()
                row = known.get(path)
                if (row and not full and row["fs_modified"] == fs_modified
                        and row["size_bytes"] == st.st_size and row["phash"]):
                    continue
                indexer.index_file(p, st, row["id"] if row else None)
                SCAN["updated" if row else "added"] += 1
            except Exception:
                SCAN["errors"] += 1

        SCAN["phase"] = "pruning"
        SCAN["removed"] = len(photo_repo.delete_absent(seen))
        SCAN["phase"] = "done"
    finally:
        SCAN["running"] = False
        SCAN["finished_at"] = datetime.now().isoformat()


def status() -> dict:
    settings = load_settings()
    return {
        "settings": settings,
        "library_exists": Path(settings["library_path"]).exists(),
        "counts": photo_repo.counts(),
        "scan": SCAN,
    }


def update_settings(patch: dict) -> dict:
    return save_settings({k: v for k, v in patch.items() if v is not None})
