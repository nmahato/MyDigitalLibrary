from fastapi import APIRouter

from ..core import BadRequest
from ..schemas import ImportPlan, ImportRunRequest, JobStarted, SourceRequest
from ..services import import_service

router = APIRouter(prefix="/api", tags=["import"])


@router.post("/import/plan", response_model=ImportPlan)
def plan(body: SourceRequest):
    result = import_service.plan(body.source)
    if "error" in result:
        raise BadRequest(result["error"])
    return result


@router.post("/import/run", response_model=JobStarted)
def run(body: ImportRunRequest):
    return import_service.start(body.source, body.dry_run)


@router.get("/import/status")
def import_status():
    return import_service.PROGRESS
