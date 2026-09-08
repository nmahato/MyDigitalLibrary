from fastapi import APIRouter
from pydantic import BaseModel

from ..services import importer

router = APIRouter(prefix="/api", tags=["import"])


class SourceBody(BaseModel):
    source: str


@router.post("/import/plan")
def plan(body: SourceBody):
    return importer.plan(body.source)


class RunBody(BaseModel):
    source: str
    dry_run: bool = False


@router.post("/import/run")
def run(body: RunBody):
    if importer.is_running():
        return {"started": False, "reason": "already running"}
    importer.start_import(body.source, body.dry_run)
    return {"started": True}


@router.get("/import/status")
def import_status():
    return importer.PROGRESS
