from fastapi import APIRouter
from pydantic import BaseModel

from ..services import tag_service

router = APIRouter(prefix="/api", tags=["tags"])


class TagName(BaseModel):
    name: str


class BulkTag(BaseModel):
    photo_ids: list[int]
    name: str


@router.get("/tags")
def list_tags():
    return tag_service.list_tags()


@router.post("/photos/{photo_id}/tags")
def add_tag(photo_id: int, body: TagName):
    return tag_service.add(photo_id, body.name)


@router.delete("/photos/{photo_id}/tags/{name}")
def remove_tag(photo_id: int, name: str):
    return tag_service.remove(photo_id, name)


@router.post("/tags/bulk")
def bulk_tag(body: BulkTag):
    return tag_service.add_many(body.photo_ids, body.name)
