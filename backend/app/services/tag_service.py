"""Business logic for hashtags."""
from ..core import BadRequest, NotFound
from ..repositories import photos as photo_repo
from ..repositories import tags as tag_repo


def list_tags() -> list[dict]:
    return [dict(r) for r in tag_repo.list_with_counts()]


def add(photo_id: int, name: str) -> dict:
    if not photo_repo.get(photo_id):
        raise NotFound("photo not found")
    tag = tag_repo.add(photo_id, name)
    if not tag:
        raise BadRequest("invalid tag")
    return {"tag": tag}


def add_many(photo_ids: list[int], name: str) -> dict:
    tag = tag_repo.add_many([p for p in photo_ids if p], name)
    if not tag:
        raise BadRequest("invalid tag")
    return {"tag": tag, "photos": len(photo_ids)}


def remove(photo_id: int, name: str) -> dict:
    tag_repo.remove(photo_id, name)
    return {"ok": True}
