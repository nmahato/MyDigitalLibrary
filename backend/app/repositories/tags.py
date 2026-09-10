"""Persistence for hashtags (`tags`, `photo_tags`)."""
import re

from ..database import get_conn

_CLEAN = re.compile(r"[^0-9a-z_\- ]+")


def normalize(name: str) -> str:
    name = (name or "").strip().lstrip("#").lower()
    name = _CLEAN.sub("", name).strip().replace(" ", "-")
    return name[:40]


def list_with_counts() -> list:
    with get_conn() as conn:
        return conn.execute("""
            SELECT t.id, t.name,
                   (SELECT COUNT(*) FROM photo_tags pt WHERE pt.tag_id=t.id) photo_count
            FROM tags t
            ORDER BY photo_count DESC, t.name
        """).fetchall()


def tags_for_photo(photo_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            "SELECT t.id, t.name FROM photo_tags pt JOIN tags t ON t.id=pt.tag_id "
            "WHERE pt.photo_id=? ORDER BY t.name", (photo_id,)).fetchall()


def _tag_id(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO tags(name) VALUES (?)", (name,)).lastrowid


def add(photo_id: int, name: str) -> str | None:
    name = normalize(name)
    if not name:
        return None
    with get_conn() as conn:
        tid = _tag_id(conn, name)
        conn.execute(
            "INSERT OR IGNORE INTO photo_tags(photo_id, tag_id) VALUES (?, ?)",
            (photo_id, tid))
    return name


def add_many(photo_ids: list[int], name: str) -> str | None:
    name = normalize(name)
    if not name or not photo_ids:
        return None
    with get_conn() as conn:
        tid = _tag_id(conn, name)
        conn.executemany(
            "INSERT OR IGNORE INTO photo_tags(photo_id, tag_id) VALUES (?, ?)",
            [(pid, tid) for pid in photo_ids])
    return name


def remove(photo_id: int, name: str) -> None:
    name = normalize(name)
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM photo_tags WHERE photo_id=? AND tag_id="
            "(SELECT id FROM tags WHERE name=?)", (photo_id, name))
        conn.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM photo_tags)")
