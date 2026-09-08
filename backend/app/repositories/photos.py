"""Persistence for the `photos` table."""
from ..database import get_conn

_SORTS = {
    "date": "taken_at",
    "name": "filename",
    "size": "size_bytes",
    "added": "indexed_at",
    "random": "RANDOM()",
}

# columns that may be written by the scanner / importer
WRITABLE = (
    "path", "rel_path", "filename", "ext", "media_type", "size_bytes",
    "width", "height", "duration_sec", "taken_at", "date_source", "fs_modified",
    "camera_make", "camera_model", "gps_lat", "gps_lon", "location",
    "orientation", "sha256", "phash", "indexed_at",
)


def _build_where(f) -> tuple[str, list, str, list]:
    """Return (join_sql, join_params, where_sql, where_params) for a PhotoFilters."""
    join, join_params = "", []
    if f.person_id:
        join = (" LEFT JOIN faces fa ON fa.photo_id=p.id AND fa.person_id=?"
                " LEFT JOIN photo_people pp ON pp.photo_id=p.id AND pp.person_id=?")
        join_params += [f.person_id, f.person_id]

    where, params = ["p.missing=0"], []
    if f.person_id:
        where.append("(fa.id IS NOT NULL OR pp.person_id IS NOT NULL)")
    if f.q:
        where.append("(p.filename LIKE ? OR p.location LIKE ? OR p.rel_path LIKE ?)")
        params += [f"%{f.q}%"] * 3
    if f.date_from:
        where.append("p.taken_at >= ?")
        params.append(f.date_from)
    if f.date_to:
        where.append("p.taken_at <= ?")
        params.append(f.date_to + "T23:59:59" if len(f.date_to) == 10 else f.date_to)
    if f.media_type in ("image", "video"):
        where.append("p.media_type = ?")
        params.append(f.media_type)
    if f.location:
        where.append("p.location = ?")
        params.append(f.location)
    if f.camera:
        where.append("(coalesce(p.camera_make,'')||' '||coalesce(p.camera_model,'')) LIKE ?")
        params.append(f"%{f.camera}%")
    if f.year:
        where.append("substr(p.taken_at,1,4) = ?")
        params.append(str(f.year))
    return join, join_params, " AND ".join(where), params


def search(f) -> tuple[int, list]:
    join, jp, where, wp = _build_where(f)
    col = _SORTS.get(f.sort, "taken_at")
    direction = "ASC" if f.order.lower() == "asc" else "DESC"
    order_sql = col if col == "RANDOM()" else f"{col} {direction}"
    all_params = jp + wp

    with get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(DISTINCT p.id) c FROM photos p{join} WHERE {where}",
            all_params,
        ).fetchone()["c"]
        rows = conn.execute(
            f"SELECT DISTINCT p.* FROM photos p{join} WHERE {where} "
            f"ORDER BY {order_sql} LIMIT ? OFFSET ?",
            all_params + [f.limit, f.offset],
        ).fetchall()
    return total, rows


def get(photo_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()


def get_many(ids: list[int]) -> list:
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    with get_conn() as conn:
        return conn.execute(
            f"SELECT * FROM photos WHERE id IN ({marks})", ids).fetchall()


def known_index() -> dict:
    """path -> row(id, size_bytes, fs_modified, phash, sha256) for incremental scans."""
    with get_conn() as conn:
        return {
            r["path"]: r
            for r in conn.execute(
                "SELECT id, path, size_bytes, fs_modified, phash, sha256 FROM photos")
        }


def known_shas() -> set[str]:
    with get_conn() as conn:
        return {
            r["sha256"]
            for r in conn.execute(
                "SELECT sha256 FROM photos WHERE sha256 IS NOT NULL")
        }


def upsert(fields: dict, existing_id: int | None) -> int:
    data = {k: v for k, v in fields.items() if k in WRITABLE}
    with get_conn() as conn:
        if existing_id:
            sets = ", ".join(f"{k}=?" for k in data)
            conn.execute(
                f"UPDATE photos SET {sets}, faces_done=0 WHERE id=?",
                (*data.values(), existing_id),
            )
            return existing_id
        cols = ", ".join(data)
        marks = ", ".join("?" * len(data))
        cur = conn.execute(
            f"INSERT INTO photos ({cols}) VALUES ({marks})", tuple(data.values()))
        return cur.lastrowid


def apply_conversion(photo_id: int, fields: dict) -> None:
    sets = ", ".join(f"{k}=?" for k in fields)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE photos SET {sets} WHERE id=?", (*fields.values(), photo_id))


def delete(ids: list[int]) -> None:
    if not ids:
        return
    with get_conn() as conn:
        conn.executemany("DELETE FROM photos WHERE id=?", [(i,) for i in ids])


def delete_absent(seen_paths: set[str]) -> list[int]:
    with get_conn() as conn:
        all_rows = conn.execute("SELECT id, path FROM photos").fetchall()
        gone = [r["id"] for r in all_rows if r["path"] not in seen_paths]
        if gone:
            conn.executemany("DELETE FROM photos WHERE id=?", [(i,) for i in gone])
    return gone


def set_rating(photo_id: int, rating: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE photos SET rating=? WHERE id=?",
                     (max(0, min(5, rating)), photo_id))


def facets() -> dict:
    with get_conn() as conn:
        years = [
            r["y"] for r in conn.execute(
                "SELECT DISTINCT substr(taken_at,1,4) y FROM photos "
                "WHERE taken_at IS NOT NULL ORDER BY y DESC")
        ]
        locations = [
            {"location": r["location"], "n": r["n"]}
            for r in conn.execute(
                "SELECT location, COUNT(*) n FROM photos WHERE location IS NOT NULL "
                "GROUP BY location ORDER BY n DESC LIMIT 200")
        ]
        cameras = [
            r["c"] for r in conn.execute(
                "SELECT DISTINCT trim(coalesce(camera_make,'')||' '||"
                "coalesce(camera_model,'')) c FROM photos "
                "WHERE camera_model IS NOT NULL ORDER BY c")
            if r["c"]
        ]
    return {"years": years, "locations": locations, "cameras": cameras}


def counts() -> dict:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT COUNT(*) total, "
            "COALESCE(SUM(media_type='image'),0) images, "
            "COALESCE(SUM(media_type='video'),0) videos, "
            "COALESCE(SUM(size_bytes),0) bytes, "
            "MIN(taken_at) earliest, MAX(taken_at) latest "
            "FROM photos WHERE missing=0").fetchone()
    return dict(r)


def dedup_rows() -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, filename, rel_path, path, size_bytes, width, height, "
            "taken_at, media_type, sha256, phash FROM photos WHERE missing=0 "
            "ORDER BY id").fetchall()
