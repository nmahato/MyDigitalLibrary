"""Exact and near-duplicate detection."""
from ..config import load_settings
from ..database import get_conn
from .hashing import hamming


def _photo_dict(r):
    return {
        "id": r["id"], "filename": r["filename"], "rel_path": r["rel_path"],
        "path": r["path"], "size_bytes": r["size_bytes"], "width": r["width"],
        "height": r["height"], "taken_at": r["taken_at"], "media_type": r["media_type"],
    }


def _quality_score(r) -> tuple:
    """Higher is better: prefer more pixels, then bigger file, then an earlier path."""
    px = (r["width"] or 0) * (r["height"] or 0)
    return (px, r["size_bytes"] or 0, -len(r["path"] or ""))


def find_groups() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM photos WHERE missing=0 ORDER BY id").fetchall()
        ignored = {(a["a"], a["b"]) for a in conn.execute("SELECT a, b FROM dup_ignored")}

    by_id = {r["id"]: r for r in rows}
    threshold = int(load_settings().get("near_duplicate_threshold", 8))

    # union-find over duplicate relations
    parent = {r["id"]: r["id"] for r in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    exact_pairs = set()
    sha_map: dict[str, list[int]] = {}
    for r in rows:
        if r["sha256"]:
            sha_map.setdefault(r["sha256"], []).append(r["id"])
    for ids in sha_map.values():
        for i in range(1, len(ids)):
            union(ids[0], ids[i])
            exact_pairs.add(frozenset((ids[0], ids[i])))

    images = [r for r in rows if r["media_type"] == "image" and r["phash"]]
    for i in range(len(images)):
        pi = images[i]
        for j in range(i + 1, len(images)):
            pj = images[j]
            if pi["sha256"] and pi["sha256"] == pj["sha256"]:
                continue
            key = (min(pi["id"], pj["id"]), max(pi["id"], pj["id"]))
            if key in ignored:
                continue
            if hamming(pi["phash"], pj["phash"]) <= threshold:
                union(pi["id"], pj["id"])

    clusters: dict[int, list[int]] = {}
    for pid in parent:
        clusters.setdefault(find(pid), []).append(pid)

    groups = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        member_rows = [by_id[m] for m in members]
        best = max(member_rows, key=_quality_score)
        exact = all(
            frozenset((a["id"], b["id"])) in exact_pairs or a["sha256"] == b["sha256"]
            for a in member_rows for b in member_rows if a["id"] < b["id"]
        )
        groups.append({
            "kind": "exact" if exact else "near",
            "suggested_keep": best["id"],
            "photos": sorted((_photo_dict(r) for r in member_rows),
                             key=lambda p: p["id"]),
            "wasted_bytes": sum(r["size_bytes"] or 0 for r in member_rows)
                            - (best["size_bytes"] or 0),
        })
    groups.sort(key=lambda g: g["wasted_bytes"], reverse=True)
    return {
        "groups": groups,
        "group_count": len(groups),
        "reclaimable_bytes": sum(g["wasted_bytes"] for g in groups),
    }


def ignore_pair(a: int, b: int):
    lo, hi = min(a, b), max(a, b)
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO dup_ignored(a, b) VALUES (?, ?)", (lo, hi))
