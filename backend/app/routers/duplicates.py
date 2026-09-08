from fastapi import APIRouter

from ..schemas import (
    AutoResolveRequest, DuplicateReport, IgnoreRequest, ResolveRequest,
)
from ..services import duplicate_service

router = APIRouter(prefix="/api", tags=["duplicates"])


@router.get("/duplicates", response_model=DuplicateReport)
def get_duplicates():
    return duplicate_service.find_groups()


@router.post("/duplicates/resolve")
def resolve(body: ResolveRequest):
    return duplicate_service.resolve(body.keep_id, body.remove_ids)


@router.post("/duplicates/ignore")
def ignore(body: IgnoreRequest):
    duplicate_service.ignore(body.a, body.b)
    return {"ok": True}


@router.post("/duplicates/auto-resolve")
def auto_resolve(body: AutoResolveRequest):
    return duplicate_service.auto_resolve(body.kinds)
