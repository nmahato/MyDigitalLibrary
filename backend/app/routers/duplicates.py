from fastapi import APIRouter
from pydantic import BaseModel

from ..database import get_conn
from ..services import duplicates
from ..services.thumbnails import thumb_file

router = APIRouter(prefix="/api", tags=["duplicates"])


@router.get("/duplicates")
def get_duplicates():
    return duplicates.find_groups()


class ResolveBody(BaseModel):
    keep_id: int
    remove_ids: list[int]


def _trash(ids: list[int]):
    from send2trash import send2trash

    removed, errors = [], []
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, path FROM photos WHERE id IN ({','.join('?' * len(ids))})",
            ids).fetchall()
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
    return removed, errors


@router.post("/duplicates/resolve")
def resolve(body: ResolveBody):
    removed, errors = _trash(body.remove_ids)
    return {"removed": removed, "errors": errors}


class IgnoreBody(BaseModel):
    a: int
    b: int


@router.post("/duplicates/ignore")
def ignore(body: IgnoreBody):
    duplicates.ignore_pair(body.a, body.b)
    return {"ok": True}


class AutoBody(BaseModel):
    kinds: list[str] = ["exact"]


@router.post("/duplicates/auto-resolve")
def auto_resolve(body: AutoBody):
    result = duplicates.find_groups()
    to_remove = []
    for g in result["groups"]:
        if g["kind"] not in body.kinds:
            continue
        for p in g["photos"]:
            if p["id"] != g["suggested_keep"]:
                to_remove.append(p["id"])
    removed, errors = _trash(to_remove) if to_remove else ([], [])
    return {"removed": removed, "errors": errors, "groups_processed": len(result["groups"])}
