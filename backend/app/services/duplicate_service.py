"""Exact + near-duplicate detection and resolution."""
from ..config import load_settings
from ..repositories import duplicates as dup_repo
from ..repositories import photos as photo_repo
from ..schemas import DuplicateGroup, DuplicatePhoto, DuplicateReport


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


def _parse_phash(val: str | None) -> int | None:
    if not val:
        return None
    try:
        return int(val, 16)
    except (ValueError, TypeError):
        return None


def find_groups() -> DuplicateReport:
    rows = photo_repo.dedup_rows()
    by_id = {r["id"]: r for r in rows}
    ignored = dup_repo.ignored_pairs()
    threshold = max(0, int(load_settings().get("near_duplicate_threshold", 8)))

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

    # Parse and filter image hashes
    parsed_images = []
    for r in rows:
        if r["media_type"] == "image":
            h_int = _parse_phash(r["phash"])
            if h_int is not None:
                parsed_images.append((r["id"], h_int, r["sha256"]))

    # Multi-Index Hashing for fast sub-linear near-duplicate matching
    if parsed_images and threshold >= 0:
        m = max(1, threshold // 2 + 1)
        chunk_defs = []
        start = 0
        for i in range(m):
            end = (64 * (i + 1)) // m
            width = end - start
            mask = (1 << width) - 1
            masks = [0] + [1 << b for b in range(width)]
            chunk_defs.append((start, mask, masks))
            start = end

        tables: list[dict[int, list[tuple[int, int, str | None]]]] = [{} for _ in range(m)]

        for pid, h, sha in parsed_images:
            for i, (shift, mask, mask_list) in enumerate(chunk_defs):
                val = (h >> shift) & mask
                tbl = tables[i]
                for mask_val in mask_list:
                    bucket = tbl.get(val ^ mask_val)
                    if bucket:
                        for other_id, other_h, other_sha in bucket:
                            if sha and sha == other_sha:
                                continue
                            key = (min(pid, other_id), max(pid, other_id))
                            if key in ignored:
                                continue
                            if (h ^ other_h).bit_count() <= threshold:
                                uf.union(pid, other_id)
                tbl.setdefault(val, []).append((pid, h, sha))

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
            frozenset((a["id"], b["id"])) in exact_pairs or (a["sha256"] and a["sha256"] == b["sha256"])
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
    result = delete(list(set(to_remove))) if to_remove else {"removed": [], "errors": []}
    result["groups_processed"] = report.group_count
    return result


def ignore(a: int, b: int) -> None:
    dup_repo.add_ignored(a, b)
