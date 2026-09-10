"""Business logic for albums (named photo collections)."""
from ..core import BadRequest, NotFound
from ..repositories import albums as album_repo
from ..repositories import photos as photo_repo


def list_albums() -> list[dict]:
    return [dict(r) for r in album_repo.list_with_counts()]


def create(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise BadRequest("album name is required")
    aid = album_repo.create(name)
    return {"id": aid, "name": name, "photo_count": 0, "cover_photo": None}


def rename(album_id: int, name: str) -> None:
    if not album_repo.get(album_id):
        raise NotFound("album not found")
    if not (name or "").strip():
        raise BadRequest("album name is required")
    album_repo.rename(album_id, name)


def delete(album_id: int) -> None:
    album_repo.delete(album_id)


def add_photos(album_id: int, photo_ids: list[int]) -> dict:
    if not album_repo.get(album_id):
        raise NotFound("album not found")
    added = album_repo.add_photos(album_id, [p for p in photo_ids if p])
    return {"added": added}


def remove_photos(album_id: int, photo_ids: list[int]) -> dict:
    album_repo.remove_photos(album_id, photo_ids)
    return {"ok": True}


def set_cover(album_id: int, photo_id: int) -> None:
    if not album_repo.get(album_id):
        raise NotFound("album not found")
    album_repo.set_cover(album_id, photo_id)


def albums_for_photo(photo_id: int) -> list[dict]:
    return [dict(r) for r in album_repo.albums_for_photo(photo_id)]
