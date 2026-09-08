"""Persistence for the duplicate-ignore list."""
from ..database import get_conn


def ignored_pairs() -> set[tuple[int, int]]:
    with get_conn() as conn:
        return {(r["a"], r["b"]) for r in conn.execute("SELECT a, b FROM dup_ignored")}


def add_ignored(a: int, b: int) -> None:
    lo, hi = min(a, b), max(a, b)
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO dup_ignored(a, b) VALUES (?, ?)", (lo, hi))
