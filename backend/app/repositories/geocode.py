"""Persistence for the reverse-geocode cache."""
from ..database import get_conn


def get_cached(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT label FROM geocode_cache WHERE key=?", (key,)).fetchone()
    return row["label"] if row else None


def put_cached(key: str, label: str | None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO geocode_cache(key, label) VALUES (?, ?)",
            (key, label))
