import io
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..database import get_conn
from ..services import faces

router = APIRouter(prefix="/api", tags=["people"])


@router.get("/people")
def list_people():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT pe.id, pe.name, pe.auto, pe.cover_face,
                   (SELECT COUNT(*) FROM faces f WHERE f.person_id=pe.id) face_count,
                   (SELECT COUNT(DISTINCT photo_id) FROM (
                        SELECT photo_id FROM faces WHERE person_id=pe.id
                        UNION SELECT photo_id FROM photo_people WHERE person_id=pe.id
                   )) photo_count
            FROM people pe ORDER BY photo_count DESC, pe.name
        """).fetchall()
    return [dict(r) for r in rows]


class PersonBody(BaseModel):
    name: str


@router.post("/people")
def create_person(body: PersonBody):
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO people(name, auto, created_at) VALUES (?, 0, ?)",
                           (body.name.strip(), datetime.now().isoformat()))
        return {"id": cur.lastrowid, "name": body.name.strip()}


@router.patch("/people/{person_id}")
def rename_person(person_id: int, body: PersonBody):
    with get_conn() as conn:
        conn.execute("UPDATE people SET name=?, auto=0 WHERE id=?",
                     (body.name.strip(), person_id))
    return {"ok": True}


@router.delete("/people/{person_id}")
def delete_person(person_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM people WHERE id=?", (person_id,))
    return {"ok": True}


class MergeBody(BaseModel):
    source_id: int
    target_id: int


@router.post("/people/merge")
def merge_people(body: MergeBody):
    if body.source_id == body.target_id:
        raise HTTPException(400, "same person")
    with get_conn() as conn:
        conn.execute("UPDATE faces SET person_id=? WHERE person_id=?",
                     (body.target_id, body.source_id))
        conn.execute("UPDATE OR IGNORE photo_people SET person_id=? WHERE person_id=?",
                     (body.target_id, body.source_id))
        conn.execute("DELETE FROM photo_people WHERE person_id=?", (body.source_id,))
        conn.execute("DELETE FROM people WHERE id=?", (body.source_id,))
    return {"ok": True}


@router.get("/people/{person_id}/faces")
def person_faces(person_id: int, limit: int = 200):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, photo_id, det_score FROM faces WHERE person_id=? "
            "ORDER BY det_score DESC LIMIT ?", (person_id, limit)).fetchall()
    return [dict(r) for r in rows]


@router.get("/faces/{face_id}/crop")
def face_crop(face_id: int):
    img = faces.crop_face(face_id)
    if img is None:
        raise HTTPException(404, "face not found")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


class AssignBody(BaseModel):
    person_id: int | None = None
    name: str | None = None


@router.post("/faces/{face_id}/assign")
def assign_face(face_id: int, body: AssignBody):
    with get_conn() as conn:
        pid = body.person_id
        if pid is None and body.name:
            row = conn.execute("SELECT id FROM people WHERE lower(name)=lower(?)",
                               (body.name.strip(),)).fetchone()
            if row:
                pid = row["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO people(name, auto, created_at) VALUES (?, 0, ?)",
                    (body.name.strip(), datetime.now().isoformat()))
                pid = cur.lastrowid
        conn.execute("UPDATE faces SET person_id=?, confirmed=1 WHERE id=?", (pid, face_id))
    return {"ok": True, "person_id": pid}


# ---- face engine control ----

@router.get("/faces/status")
def faces_status():
    return faces.status()


class DetectBody(BaseModel):
    limit: int | None = None


@router.post("/faces/detect")
def detect(body: DetectBody):
    if not faces.available():
        raise HTTPException(503, "face engine not installed (pip install -r requirements-faces.txt)")
    if faces.is_running():
        return {"started": False, "reason": "already running"}
    faces.start_detection(body.limit)
    return {"started": True}


@router.post("/faces/cluster")
def recluster():
    faces.cluster_unassigned()
    return {"ok": True}


# ---- photo-level people tags (no face model needed) ----

class TagBody(BaseModel):
    person_id: int


@router.post("/photos/{photo_id}/people")
def tag_photo(photo_id: int, body: TagBody):
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO photo_people(photo_id, person_id) VALUES (?, ?)",
                     (photo_id, body.person_id))
    return {"ok": True}


@router.delete("/photos/{photo_id}/people/{person_id}")
def untag_photo(photo_id: int, person_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM photo_people WHERE photo_id=? AND person_id=?",
                     (photo_id, person_id))
    return {"ok": True}
