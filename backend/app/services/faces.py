"""On-device face detection + clustering. Degrades gracefully when InsightFace is absent."""
import threading
from datetime import datetime

import numpy as np
from PIL import Image, ImageOps

from ..database import get_conn
from . import imaging  # noqa: F401  (configures Pillow)

PROGRESS = {"running": False, "phase": "idle", "total": 0, "done": 0,
            "faces_found": 0, "finished_at": None}

_app = None
_load_error = None


def available() -> bool:
    return _try_load() is not None


def _try_load():
    global _app, _load_error
    if _app is not None:
        return _app
    if _load_error is not None:
        return None
    try:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _app = app
        return _app
    except Exception as e:  # noqa: BLE001
        _load_error = str(e)
        return None


def status() -> dict:
    with get_conn() as conn:
        faces = conn.execute("SELECT COUNT(*) c FROM faces").fetchone()["c"]
        named = conn.execute(
            "SELECT COUNT(*) c FROM faces WHERE person_id IS NOT NULL").fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) c FROM photos WHERE media_type='image' AND faces_done=0"
        ).fetchone()["c"]
    return {
        "engine_available": available(),
        "load_error": _load_error,
        "faces": faces, "named_faces": named, "photos_pending": pending,
        "progress": PROGRESS,
    }


def is_running():
    return PROGRESS["running"]


def start_detection(limit: int | None = None):
    if PROGRESS["running"]:
        return
    threading.Thread(target=_detect_all, args=(limit,), daemon=True).start()


def _detect_all(limit):
    app = _try_load()
    PROGRESS.update(running=True, phase="detecting", total=0, done=0,
                    faces_found=0, finished_at=None)
    try:
        if app is None:
            PROGRESS["phase"] = f"face engine unavailable: {_load_error}"
            return
        with get_conn() as conn:
            q = "SELECT id, path FROM photos WHERE media_type='image' AND faces_done=0 ORDER BY taken_at DESC"
            if limit:
                q += f" LIMIT {int(limit)}"
            todo = conn.execute(q).fetchall()
        PROGRESS["total"] = len(todo)

        for row in todo:
            PROGRESS["done"] += 1
            try:
                faces = _detect_one(app, row["id"], row["path"])
                PROGRESS["faces_found"] += faces
            except Exception:
                pass
            with get_conn() as conn:
                conn.execute("UPDATE photos SET faces_done=1 WHERE id=?", (row["id"],))

        PROGRESS["phase"] = "clustering"
        cluster_unassigned()
        PROGRESS["phase"] = "done"
    finally:
        PROGRESS["running"] = False
        PROGRESS["finished_at"] = datetime.now().isoformat()


def _detect_one(app, photo_id: int, path: str) -> int:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        arr = np.asarray(im)[:, :, ::-1]  # RGB -> BGR
    faces = app.get(arr)
    with get_conn() as conn:
        conn.execute("DELETE FROM faces WHERE photo_id=? AND person_id IS NULL", (photo_id,))
        for f in faces:
            x1, y1, x2, y2 = [int(v) for v in f.bbox]
            emb = np.asarray(f.normed_embedding, dtype=np.float32).tobytes()
            conn.execute(
                """INSERT INTO faces
                   (photo_id, bbox_x, bbox_y, bbox_w, bbox_h, det_score, embedding)
                   VALUES (?,?,?,?,?,?,?)""",
                (photo_id, x1, y1, x2 - x1, y2 - y1, float(f.det_score), emb),
            )
    return len(faces)


def _load_embeddings(where: str = ""):
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, person_id, embedding FROM faces WHERE embedding IS NOT NULL {where}"
        ).fetchall()
    ids, vecs, persons = [], [], []
    for r in rows:
        ids.append(r["id"])
        persons.append(r["person_id"])
        vecs.append(np.frombuffer(r["embedding"], dtype=np.float32))
    if not vecs:
        return np.array([]), np.zeros((0, 512)), np.array([])
    return np.array(ids), np.vstack(vecs), np.array(persons, dtype=object)


def cluster_unassigned(eps: float = 0.45, min_samples: int = 2):
    ids, vecs, persons = _load_embeddings()
    if len(ids) == 0:
        return

    # 1. attach to an existing named person if close to its centroid
    named_ids = [i for i, p in enumerate(persons) if p is not None]
    centroids = {}
    if named_ids:
        for pid in set(persons[i] for i in named_ids):
            idx = [i for i in named_ids if persons[i] == pid]
            centroids[pid] = _norm(vecs[idx].mean(axis=0))

    free = [i for i, p in enumerate(persons) if p is None]
    assigned = {}
    for i in list(free):
        best_pid, best_sim = None, 0.0
        for pid, c in centroids.items():
            sim = float(np.dot(_norm(vecs[i]), c))
            if sim > best_sim:
                best_pid, best_sim = pid, sim
        if best_sim >= 0.55:
            assigned[ids[i]] = best_pid

    if assigned:
        with get_conn() as conn:
            conn.executemany("UPDATE faces SET person_id=? WHERE id=?",
                             [(p, fid) for fid, p in assigned.items()])
        free = [i for i in free if ids[i] not in assigned]

    if not free:
        return

    sub_vecs = vecs[free]
    labels = _dbscan_cosine(sub_vecs, eps, min_samples)

    with get_conn() as conn:
        for lbl in sorted(set(labels)):
            members = [ids[free[k]] for k in range(len(free)) if labels[k] == lbl]
            if lbl == -1 or len(members) < min_samples:
                conn.executemany("UPDATE faces SET cluster_id=NULL WHERE id=?",
                                 [(m,) for m in members])
                continue
            cur = conn.execute(
                "INSERT INTO people(name, auto, created_at) VALUES (?, 1, ?)",
                (f"Person {datetime.now():%m%d}-{lbl + 1}", datetime.now().isoformat()),
            )
            new_pid = cur.lastrowid
            conn.executemany(
                "UPDATE faces SET person_id=?, cluster_id=? WHERE id=?",
                [(new_pid, lbl, m) for m in members],
            )
            conn.execute("UPDATE people SET cover_face=? WHERE id=?",
                         (members[0], new_pid))


def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n else v


def _dbscan_cosine(vecs: np.ndarray, eps: float, min_samples: int):
    try:
        from sklearn.cluster import DBSCAN

        v = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
        return DBSCAN(eps=eps, min_samples=min_samples, metric="cosine").fit_predict(v)
    except Exception:
        return _greedy_cluster(vecs, 1 - eps, min_samples)


def _greedy_cluster(vecs, sim_threshold, min_samples):
    v = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    n = len(v)
    labels = [-1] * n
    cur = 0
    for i in range(n):
        if labels[i] != -1:
            continue
        sims = v @ v[i]
        members = [j for j in range(n) if sims[j] >= sim_threshold]
        if len(members) >= min_samples:
            for j in members:
                if labels[j] == -1:
                    labels[j] = cur
            cur += 1
    return np.array(labels)


def crop_face(face_id: int):
    with get_conn() as conn:
        f = conn.execute(
            """SELECT f.*, p.path FROM faces f JOIN photos p ON p.id=f.photo_id
               WHERE f.id=?""", (face_id,)).fetchone()
    if not f:
        return None
    with Image.open(f["path"]) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        pad_x, pad_y = f["bbox_w"] // 4, f["bbox_h"] // 4
        box = (max(0, f["bbox_x"] - pad_x), max(0, f["bbox_y"] - pad_y),
               f["bbox_x"] + f["bbox_w"] + pad_x, f["bbox_y"] + f["bbox_h"] + pad_y)
        return im.crop(box)
