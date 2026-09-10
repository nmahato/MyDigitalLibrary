"""Persistence for `albums` and `album_photos`."""
from datetime import datetime

from ..database import get_conn


def list_with_counts() -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT a.id, a.name, a.cover_photo, a.created_at,
                   (SELECT COUNT(*) FROM album_photos ap WHERE ap.album_id=a.id) photo_count
            FROM albums a ORDER BY a.name COLLATE NOCASE
        """).fetchall()


def get(album_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM albums WHERE id=?", (album_id,)).fetchone()


def create(name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO albums(name, created_at) VALUES (?, ?)",
            (name.strip(), datetime.now().isoformat()))
        return cur.lastrowid


def rename(album_id: int, name: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE albums SET name=? WHERE id=?", (name.strip(), album_id))


def delete(album_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM albums WHERE id=?", (album_id,))


def set_cover(album_id: int, photo_id: int | None) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE albums SET cover_photo=? WHERE id=?", (photo_id, album_id))


def add_photos(album_id: int, photo_ids: list[int]) -> int:
    now = datetime.now().isoformat()
    with get_conn() as conn:
        before = conn.execute(
            "SELECT COUNT(*) c FROM album_photos WHERE album_id=?", (album_id,)
        ).fetchone()["c"]
        conn.executemany(
            "INSERT OR IGNORE INTO album_photos(album_id, photo_id, added_at) "
            "VALUES (?, ?, ?)", [(album_id, pid, now) for pid in photo_ids])
        row = conn.execute(
            "SELECT COUNT(*) c, MIN(photo_id) first FROM album_photos WHERE album_id=?",
            (album_id,)).fetchone()
        if row["c"] and not get(album_id)["cover_photo"]:
            conn.execute("UPDATE albums SET cover_photo=? WHERE id=?",
                         (row["first"], album_id))
        return row["c"] - before


def remove_photos(album_id: int, photo_ids: list[int]) -> None:
    if not photo_ids:
        return
    marks = ",".join("?" * len(photo_ids))
    with get_conn() as conn:
        conn.execute(
            f"DELETE FROM album_photos WHERE album_id=? AND photo_id IN ({marks})",
            (album_id, *photo_ids))


def albums_for_photo(photo_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT a.id, a.name FROM album_photos ap JOIN albums a ON a.id=ap.album_id "
            "WHERE ap.photo_id=? ORDER BY a.name COLLATE NOCASE", (photo_id,)).fetchall()
