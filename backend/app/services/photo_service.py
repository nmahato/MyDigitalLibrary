"""Business logic for browsing, inspecting and removing photos."""
from ..core import NotFound, move_to_trash
from ..repositories import people as people_repo
from ..repositories import photos as photo_repo
from ..services.thumbnails import thumb_file

_HIDDEN = {"indexed_at", "fs_modified", "faces_done", "missing"}


def _public(row) -> dict:
    return {k: v for k, v in dict(row).items() if k not in _HIDDEN}


def search(filters) -> dict:
    total, rows = photo_repo.search(filters)
    items = [_public(r) for r in rows]

    if filters.duplicates_only:
        from .duplicate_service import find_groups

        dup_ids = {p["id"] for g in find_groups().groups for p in g.photos}
        items = [i for i in items if i["id"] in dup_ids]
        total = len(items)

    return {"total": total, "items": items,
            "limit": filters.limit, "offset": filters.offset}


def facets() -> dict:
    data = photo_repo.facets()
    c = photo_repo.counts()
    data["counts"] = {
        "total": c["total"], "images": c["images"],
        "videos": c["videos"], "bytes": c["bytes"],
    }
    return data


def get_detail(photo_id: int) -> dict:
    row = photo_repo.get(photo_id)
    if not row:
        raise NotFound("photo not found")
    data = _public(row)
    data["faces"] = [dict(f) for f in people_repo.faces_for_photo(photo_id)]
    data["people_tags"] = [dict(t) for t in people_repo.tags_for_photo(photo_id)]
    return data


def require_path(photo_id: int) -> tuple[str, str]:
    row = photo_repo.get(photo_id)
    if not row:
        raise NotFound("photo not found")
    return row["path"], row["media_type"]


def delete(ids: list[int]) -> dict:
    rows = photo_repo.get_many(ids)
    if not rows:
        return {"removed": [], "errors": []}

    by_path = {r["path"]: r["id"] for r in rows}
    ok_paths, errors = move_to_trash(list(by_path))
    removed = [by_path[p] for p in ok_paths]

    photo_repo.delete(removed)
    for pid in removed:
        tf = thumb_file(pid)
        if tf.exists():
            tf.unlink()
    return {"removed": removed, "errors": errors}


def set_rating(photo_id: int, rating: int) -> None:
    if not photo_repo.get(photo_id):
        raise NotFound("photo not found")
    photo_repo.set_rating(photo_id, rating)
