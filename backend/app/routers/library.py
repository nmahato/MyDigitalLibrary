from fastapi import APIRouter

from ..repositories import photos as photo_repo
from ..schemas import (
    FolderNode, JobStarted, LibraryStatus, ScanRequest, Settings, SettingsPatch,
)
from ..services import library_service

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/library/folders", response_model=list[FolderNode])
def folders():
    return photo_repo.folder_tree()


@router.get("/library/status", response_model=LibraryStatus)
def status():
    return library_service.status()


@router.post("/library/scan", response_model=JobStarted)
def scan(body: ScanRequest):
    return library_service.start_scan(full=body.full)


@router.get("/library/scan")
def scan_progress():
    return library_service.SCAN


@router.post("/settings", response_model=Settings)
def update_settings(body: SettingsPatch):
    return library_service.update_settings(body.model_dump())
