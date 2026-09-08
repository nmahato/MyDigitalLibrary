from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import load_settings, save_settings
from ..database import get_conn
from ..services import scanner

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/library/status")
def status():
    with get_conn() as conn:
        c = conn.execute(
            "SELECT COUNT(*) total, SUM(media_type='image') images, "
            "SUM(media_type='video') videos, SUM(size_bytes) bytes, "
            "MIN(taken_at) earliest, MAX(taken_at) latest FROM photos WHERE missing=0"
        ).fetchone()
    settings = load_settings()
    return {
        "settings": settings,
        "library_exists": Path(settings["library_path"]).exists(),
        "counts": dict(c),
        "scan": scanner.PROGRESS,
    }


class ScanBody(BaseModel):
    full: bool = False


@router.post("/library/scan")
def scan(body: ScanBody):
    if scanner.is_running():
        return {"started": False, "reason": "already running"}
    scanner.start_scan(full=body.full)
    return {"started": True}


@router.get("/library/scan")
def scan_progress():
    return scanner.PROGRESS


class SettingsBody(BaseModel):
    library_path: str | None = None
    import_mode: str | None = None
    near_duplicate_threshold: int | None = None
    geocode: str | None = None
    nominatim_email: str | None = None


@router.post("/settings")
def update_settings(body: SettingsBody):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    return save_settings(patch)
