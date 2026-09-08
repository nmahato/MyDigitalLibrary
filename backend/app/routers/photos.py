from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..database import get_conn
from ..media import file_response
from ..services.thumbnails import ensure_thumb, thumb_file

router = APIRouter(prefix="/api", tags=["photos"])

_SORTS = {
    "date": "taken_at", "name": "filename", "size": "size_bytes",
    "added": "indexed_at", "random": "RANDOM()",
}


@router.get("/photos")
def list_photos(
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    media_type: str | None = None,
    location: str | None = None,
    camera: str | None = None,
    person_id: int | None = None,
    year: int | None = None,
    duplicates_only: bool = False,
    sort: str = "date",
    order: str = "desc",
    limit: int = Query(120, le=500),
    offset: int = 0,
):
    join_params: list = []
    join = ""
    if person_id:
        join = (" LEFT JOIN faces f ON f.photo_id=p.id AND f.person_id=?"
                " LEFT JOIN photo_people pp ON pp.photo_id=p.id AND pp.person_id=?")
        join_params += [person_id, person_id]

    where, params = ["p.missing=0"], []
    if person_id:
        where.append("(f.id IS NOT NULL OR pp.person_id IS NOT NULL)")
    if q:
        where.append("(p.filename LIKE ? OR p.location LIKE ? OR p.rel_path LIKE ?)")
        params += [f"%{q}%"] * 3
    if date_from:
        where.append("p.taken_at >= ?")
        params.append(date_from)
    if date_to:
        where.append("p.taken_at <= ?")
        params.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)
    if media_type in ("image", "video"):
        where.append("p.media_type = ?")
        params.append(media_type)
    if location:
        where.append("p.location = ?")
        params.append(location)
    if camera:
        where.append("(coalesce(p.camera_make,'') || ' ' || coalesce(p.camera_model,'')) LIKE ?")
        params.append(f"%{camera}%")
    if year:
        where.append("substr(p.taken_at,1,4) = ?")
        params.append(str(year))

    order_col = _SORTS.get(sort, "taken_at")
    order_dir = "ASC" if order.lower() == "asc" else "DESC"
    order_sql = order_col if order_col == "RANDOM()" else f"{order_col} {order_dir}"

    all_params = join_params + params
    sql = f"SELECT DISTINCT p.* FROM photos p{join} WHERE {' AND '.join(where)}"
    count_sql = f"SELECT COUNT(DISTINCT p.id) c FROM photos p{join} WHERE {' AND '.join(where)}"

    with get_conn() as conn:
        total = conn.execute(count_sql, all_params).fetchone()["c"]
        rows = conn.execute(
            sql + f" ORDER BY {order_sql} LIMIT ? OFFSET ?",
            all_params + [limit, offset],
        ).fetchall()

    items = [_row(r) for r in rows]
    if duplicates_only:
        from ..services.duplicates import find_groups

        dup_ids = {p["id"] for g in find_groups()["groups"] for p in g["photos"]}
        items = [i for i in items if i["id"] in dup_ids]
        total = len(items)
    return {"total": total, "items": items, "limit": limit, "offset": offset}


@router.get("/photos/facets")
def facets():
    with get_conn() as conn:
        years = [r["y"] for r in conn.execute(
            "SELECT DISTINCT substr(taken_at,1,4) y FROM photos WHERE taken_at IS NOT NULL ORDER BY y DESC")]
        locations = [dict(r) for r in conn.execute(
            "SELECT location, COUNT(*) n FROM photos WHERE location IS NOT NULL "
            "GROUP BY location ORDER BY n DESC LIMIT 200")]
        cameras = [r["c"] for r in conn.execute(
            "SELECT DISTINCT trim(coalesce(camera_make,'')||' '||coalesce(camera_model,'')) c "
            "FROM photos WHERE camera_model IS NOT NULL ORDER BY c")]
        counts = conn.execute(
            "SELECT COUNT(*) total, "
            "SUM(media_type='image') images, SUM(media_type='video') videos, "
            "SUM(size_bytes) bytes FROM photos WHERE missing=0").fetchone()
    return {"years": years, "locations": locations, "cameras": [c for c in cameras if c],
            "counts": dict(counts)}


@router.get("/photos/{photo_id}")
def get_photo(photo_id: int):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
        if not r:
            raise HTTPException(404, "not found")
        faces = [dict(f) for f in conn.execute(
            "SELECT f.id, f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, f.person_id, pe.name "
            "FROM faces f LEFT JOIN people pe ON pe.id=f.person_id WHERE f.photo_id=?",
            (photo_id,))]
        tags = [dict(t) for t in conn.execute(
            "SELECT pe.id, pe.name FROM photo_people pp JOIN people pe ON pe.id=pp.person_id "
            "WHERE pp.photo_id=?", (photo_id,))]
    d = _row(r)
    d["faces"] = faces
    d["people_tags"] = tags
    return d


@router.get("/photos/{photo_id}/thumb")
def photo_thumb(photo_id: int):
    with get_conn() as conn:
        r = conn.execute("SELECT path, media_type FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not r:
        raise HTTPException(404, "not found")
    t = ensure_thumb(photo_id, r["path"], r["media_type"])
    if not t:
        raise HTTPException(404, "no thumbnail")
    return FileResponse(t, media_type="image/webp")


@router.get("/photos/{photo_id}/file")
def photo_file(photo_id: int, request: Request):
    with get_conn() as conn:
        r = conn.execute("SELECT path FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not r:
        raise HTTPException(404, "not found")
    return file_response(r["path"], request)


@router.get("/photos/{photo_id}/download")
def photo_download(photo_id: int, request: Request):
    with get_conn() as conn:
        r = conn.execute("SELECT path FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not r:
        raise HTTPException(404, "not found")
    return file_response(r["path"], request, download=True)


class DeleteBody(BaseModel):
    ids: list[int]


@router.post("/photos/delete")
def delete_photos(body: DeleteBody):
    from send2trash import send2trash

    removed, errors = [], []
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, path FROM photos WHERE id IN ({','.join('?' * len(body.ids))})",
            body.ids).fetchall()
    for r in rows:
        try:
            send2trash(r["path"])
            with get_conn() as conn:
                conn.execute("DELETE FROM photos WHERE id=?", (r["id"],))
            tf = thumb_file(r["id"])
            if tf.exists():
                tf.unlink()
            removed.append(r["id"])
        except Exception as e:  # noqa: BLE001
            errors.append({"id": r["id"], "error": str(e)})
    return {"removed": removed, "errors": errors}


class RatingBody(BaseModel):
    rating: int


@router.patch("/photos/{photo_id}/rating")
def set_rating(photo_id: int, body: RatingBody):
    with get_conn() as conn:
        conn.execute("UPDATE photos SET rating=? WHERE id=?",
                     (max(0, min(5, body.rating)), photo_id))
    return {"ok": True}


def _row(r) -> dict:
    d = dict(r)
    d.pop("indexed_at", None)
    return d
