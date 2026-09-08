"""Exact + near-duplicate detection and resolution."""
from ..config import load_settings
from ..repositories import duplicates as dup_repo
from ..repositories import photos as photo_repo
from ..schemas import DuplicateGroup, DuplicatePhoto, DuplicateReport
from .hashing import hamming


class _UnionFind:
    def __init__(self, ids):
        self.parent = {i: i for i in ids}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _quality(row) -> tuple:
    px = (row["width"] or 0) * (row["height"] or 0)
    return (px, row["size_bytes"] or 0, -len(row["path"] or ""))


def find_groups() -> DuplicateReport:
    rows = photo_repo.dedup_rows()
    by_id = {r["id"]: r for r in rows}
    ignored = dup_repo.ignored_pairs()
    threshold = int(load_settings().get("near_duplicate_threshold", 8))

    uf = _UnionFind(by_id)
    exact_pairs: set[frozenset] = set()

    sha_map: dict[str, list[int]] = {}
    for r in rows:
        if r["sha256"]:
            sha_map.setdefault(r["sha256"], []).append(r["id"])
    for ids in sha_map.values():
        for other in ids[1:]:
            uf.union(ids[0], other)
            exact_pairs.add(frozenset((ids[0], other)))

    images = [r for r in rows if r["media_type"] == "image" and r["phash"]]
    for i, pi in enumerate(images):
        for pj in images[i + 1:]:
            if pi["sha256"] and pi["sha256"] == pj["sha256"]:
                continue
            key = (min(pi["id"], pj["id"]), max(pi["id"], pj["id"]))
            if key in ignored:
                continue
            if hamming(pi["phash"], pj["phash"]) <= threshold:
                uf.union(pi["id"], pj["id"])

    clusters: dict[int, list[int]] = {}
    for pid in uf.parent:
        clusters.setdefault(uf.find(pid), []).append(pid)

    groups: list[DuplicateGroup] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        member_rows = [by_id[m] for m in members]
        best = max(member_rows, key=_quality)
        is_exact = all(
            frozenset((a["id"], b["id"])) in exact_pairs or a["sha256"] == b["sha256"]
            for a in member_rows for b in member_rows if a["id"] < b["id"]
        )
        groups.append(DuplicateGroup(
            kind="exact" if is_exact else "near",
            suggested_keep=best["id"],
            photos=[
                DuplicatePhoto(
                    id=r["id"], filename=r["filename"], rel_path=r["rel_path"],
                    path=r["path"], size_bytes=r["size_bytes"], width=r["width"],
                    height=r["height"], taken_at=r["taken_at"], media_type=r["media_type"],
                )
                for r in sorted(member_rows, key=lambda r: r["id"])
            ],
            wasted_bytes=sum(r["size_bytes"] or 0 for r in member_rows)
            - (best["size_bytes"] or 0),
        ))

    groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
    return DuplicateReport(
        groups=groups,
        group_count=len(groups),
        reclaimable_bytes=sum(g.wasted_bytes for g in groups),
    )


def resolve(keep_id: int, remove_ids: list[int]) -> dict:
    from .photo_service import delete

    remove = [i for i in remove_ids if i != keep_id]
    return delete(remove)


def auto_resolve(kinds: list[str]) -> dict:
    from .photo_service import delete

    report = find_groups()
    to_remove: list[int] = []
    for g in report.groups:
        if g.kind in kinds:
            to_remove += [p.id for p in g.photos if p.id != g.suggested_keep]
    result = delete(to_remove) if to_remove else {"removed": [], "errors": []}
    result["groups_processed"] = report.group_count
    return result


def ignore(a: int, b: int) -> None:
    dup_repo.add_ignored(a, b)
