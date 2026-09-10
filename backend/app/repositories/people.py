"""Persistence for `people`, `faces` and `photo_people`."""
from datetime import datetime

from ..database import get_conn


# ---------- people ----------

def list_with_counts() -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT pe.id, pe.name, pe.auto, pe.cover_face,
                   (SELECT COUNT(*) FROM faces f WHERE f.person_id=pe.id) face_count,
                   (SELECT COUNT(*) FROM faces f WHERE f.person_id=pe.id AND f.confirmed=1) confirmed_count,
                   (SELECT COUNT(*) FROM faces f WHERE f.person_id=pe.id AND f.confirmed=0) suggested_count,
                   (SELECT COUNT(DISTINCT photo_id) FROM (
                        SELECT photo_id FROM faces WHERE person_id=pe.id
                        UNION SELECT photo_id FROM photo_people WHERE person_id=pe.id
                   )) photo_count
            FROM people pe ORDER BY pe.auto, photo_count DESC, pe.name
        """).fetchall()


def get(person_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()


def find_by_name(name: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM people WHERE lower(name)=lower(?)", (name.strip(),)).fetchone()


def create(name: str, *, auto: bool = False) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO people(name, auto, created_at) VALUES (?, ?, ?)",
            (name.strip(), 1 if auto else 0, datetime.now().isoformat()))
        return cur.lastrowid


def rename(person_id: int, name: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE people SET name=?, auto=0 WHERE id=?",
                     (name.strip(), person_id))


def delete(person_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM people WHERE id=?", (person_id,))


def set_cover(person_id: int, face_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE people SET cover_face=? WHERE id=?", (face_id, person_id))


def merge(source_id: int, target_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE faces SET person_id=? WHERE person_id=?",
                     (target_id, source_id))
        conn.execute("UPDATE OR IGNORE photo_people SET person_id=? WHERE person_id=?",
                     (target_id, source_id))
        conn.execute("DELETE FROM photo_people WHERE person_id=?", (source_id,))
        conn.execute("DELETE FROM people WHERE id=?", (source_id,))


# ---------- faces ----------

def faces_for_photo(photo_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT f.id, f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, f.person_id, "
            "f.confirmed, f.similarity, pe.name, pe.auto "
            "FROM faces f LEFT JOIN people pe ON pe.id=f.person_id "
            "WHERE f.photo_id=? ORDER BY f.bbox_x", (photo_id,)).fetchall()


def faces_for_person(person_id: int, *, status: str = "all", limit: int = 300) -> list:
    where = "person_id=?"
    if status == "confirmed":
        where += " AND confirmed=1"
    elif status == "suggested":
        where += " AND confirmed=0"
    order = "confirmed DESC, similarity DESC, det_score DESC"
    with get_conn() as conn:
        return conn.execute(
            f"SELECT id, photo_id, det_score, confirmed, similarity FROM faces "
            f"WHERE {where} ORDER BY {order} LIMIT ?",
            (person_id, limit)).fetchall()


def face_with_photo(face_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT f.*, p.path FROM faces f JOIN photos p ON p.id=f.photo_id "
            "WHERE f.id=?", (face_id,)).fetchone()


def replace_unassigned_faces(photo_id: int, faces: list[dict]) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM faces WHERE photo_id=? AND person_id IS NULL", (photo_id,))
        for f in faces:
            conn.execute(
                "INSERT INTO faces (photo_id, bbox_x, bbox_y, bbox_w, bbox_h, "
                "det_score, embedding) VALUES (?,?,?,?,?,?,?)",
                (photo_id, f["x"], f["y"], f["w"], f["h"], f["score"], f["embedding"]))


def mark_photo_faces_done(photo_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE photos SET faces_done=1 WHERE id=?", (photo_id,))


def photos_pending_faces(limit: int | None = None) -> list:
    q = ("SELECT id, path FROM photos WHERE media_type='image' AND faces_done=0 "
         "ORDER BY taken_at DESC")
    if limit:
        q += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return conn.execute(q).fetchall()


def load_embeddings() -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, person_id, confirmed, embedding FROM faces "
            "WHERE embedding IS NOT NULL").fetchall()


def unassigned_embeddings() -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, embedding FROM faces "
            "WHERE person_id IS NULL AND embedding IS NOT NULL").fetchall()


def person_embeddings(*, confirmed_only: bool) -> list:
    q = ("SELECT f.person_id, pe.auto, f.confirmed, f.embedding "
         "FROM faces f JOIN people pe ON pe.id=f.person_id "
         "WHERE f.embedding IS NOT NULL")
    if confirmed_only:
        q += " AND f.confirmed=1"
    with get_conn() as conn:
        return conn.execute(q).fetchall()


def get_face(face_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM faces WHERE id=?", (face_id,)).fetchone()


def assign_faces(pairs: list[tuple[int | None, int]]) -> None:
    """pairs of (person_id, face_id)."""
    with get_conn() as conn:
        conn.executemany("UPDATE faces SET person_id=? WHERE id=?", pairs)


def apply_recognition(rows: list[tuple[int, float, int]]) -> None:
    """rows of (person_id, similarity, face_id) — suggestions (confirmed=0)."""
    with get_conn() as conn:
        conn.executemany(
            "UPDATE faces SET person_id=?, similarity=?, confirmed=0 WHERE id=?", rows)


def assign_face(face_id: int, person_id: int | None, *, confirmed: bool = True) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE faces SET person_id=?, confirmed=?, similarity=NULL WHERE id=?",
            (person_id, 1 if confirmed else 0, face_id))


def confirm_face(face_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE faces SET confirmed=1 WHERE id=?", (face_id,))


def confirm_person_faces(person_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE faces SET confirmed=1, similarity=NULL WHERE person_id=?",
            (person_id,))


def detach_face(face_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE faces SET person_id=NULL, confirmed=0, cluster_id=NULL, "
            "similarity=NULL WHERE id=?", (face_id,))


def count_auto_people() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM people WHERE auto=1").fetchone()["c"]


def delete_empty_auto_people() -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM people WHERE auto=1 AND id NOT IN "
            "(SELECT DISTINCT person_id FROM faces WHERE person_id IS NOT NULL)")
        return cur.rowcount


def set_cluster(face_ids: list[int], cluster_id: int | None) -> None:
    with get_conn() as conn:
        conn.executemany("UPDATE faces SET cluster_id=? WHERE id=?",
                         [(cluster_id, fid) for fid in face_ids])


def assign_cluster(face_ids: list[int], person_id: int, cluster_id: int) -> None:
    with get_conn() as conn:
        conn.executemany(
            "UPDATE faces SET person_id=?, cluster_id=? WHERE id=?",
            [(person_id, cluster_id, fid) for fid in face_ids])


def face_stats() -> dict:
    with get_conn() as conn:
        faces = conn.execute("SELECT COUNT(*) c FROM faces").fetchone()["c"]
        named = conn.execute(
            "SELECT COUNT(*) c FROM faces f JOIN people pe ON pe.id=f.person_id "
            "WHERE pe.auto=0").fetchone()["c"]
        unassigned = conn.execute(
            "SELECT COUNT(*) c FROM faces WHERE person_id IS NULL").fetchone()["c"]
        suggested = conn.execute(
            "SELECT COUNT(*) c FROM faces WHERE person_id IS NOT NULL AND confirmed=0"
        ).fetchone()["c"]
        groups = conn.execute(
            "SELECT COUNT(*) c FROM people WHERE auto=1").fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) c FROM photos WHERE media_type='image' AND faces_done=0"
        ).fetchone()["c"]
    return {"faces": faces, "named_faces": named, "unassigned_faces": unassigned,
            "suggested_faces": suggested, "unnamed_groups": groups,
            "photos_pending": pending}


# ---------- photo-level tags ----------

def tags_for_photo(photo_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT pe.id, pe.name FROM photo_people pp "
            "JOIN people pe ON pe.id=pp.person_id WHERE pp.photo_id=?",
            (photo_id,)).fetchall()


def add_tag(photo_id: int, person_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO photo_people(photo_id, person_id) VALUES (?, ?)",
            (photo_id, person_id))


def remove_tag(photo_id: int, person_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM photo_people WHERE photo_id=? AND person_id=?",
            (photo_id, person_id))
