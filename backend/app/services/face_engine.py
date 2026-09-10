"""On-device face detection + clustering. Degrades gracefully without InsightFace."""
import ssl
import threading
import urllib.request
import zipfile
from datetime import datetime

import numpy as np
from PIL import Image, ImageOps

from ..config import INSIGHTFACE_ROOT
from ..repositories import people as people_repo
from . import imaging  # noqa: F401

_MODEL = "buffalo_l"
_MODEL_URL = (
    "https://github.com/deepinsight/insightface/releases/download/"
    "model-zoo/buffalo_l.zip"
)

PROGRESS = {"running": False, "phase": "idle", "total": 0, "done": 0,
            "faces_found": 0, "finished_at": None}

_app = None
_load_error: str | None = None


def available() -> bool:
    return _try_load() is not None


def _ensure_model() -> None:
    """Make sure the model bundle exists under INSIGHTFACE_ROOT/models/<name>."""
    dest = INSIGHTFACE_ROOT / "models" / _MODEL
    if (dest / "det_10g.onnx").exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    zip_path = INSIGHTFACE_ROOT / "models" / f"{_MODEL}.zip"
    ctx = ssl.create_default_context()
    try:  # first try verified, then fall back (corporate MITM certs, etc.)
        _download(_MODEL_URL, zip_path, ctx)
    except Exception:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _download(_MODEL_URL, zip_path, ctx)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    zip_path.unlink(missing_ok=True)


def _download(url: str, path, ctx) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "PhotoLibraryViewer"})
    with urllib.request.urlopen(req, context=ctx, timeout=120) as r, open(path, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def _try_load():
    global _app, _load_error
    if _app is not None:
        return _app
    if _load_error is not None:
        return None
    try:
        from insightface.app import FaceAnalysis

        _ensure_model()
        app = FaceAnalysis(name=_MODEL, root=str(INSIGHTFACE_ROOT),
                           allowed_modules=["detection", "recognition"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _app = app
        return _app
    except Exception as e:  # noqa: BLE001
        _load_error = str(e)
        return None


def status() -> dict:
    return {
        "engine_available": available(),
        "load_error": _load_error,
        **people_repo.face_stats(),
        "progress": PROGRESS,
    }


def running() -> bool:
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
        todo = people_repo.photos_pending_faces(limit)
        PROGRESS["total"] = len(todo)
        for row in todo:
            PROGRESS["done"] += 1
            try:
                PROGRESS["faces_found"] += _detect_one(app, row["id"], row["path"])
            except Exception:
                pass
            people_repo.mark_photo_faces_done(row["id"])

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
    detected = app.get(arr)
    faces = []
    for f in detected:
        x1, y1, x2, y2 = [int(v) for v in f.bbox]
        faces.append({
            "x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1,
            "score": float(f.det_score),
            "embedding": np.asarray(f.normed_embedding, dtype=np.float32).tobytes(),
        })
    people_repo.replace_unassigned_faces(photo_id, faces)
    return len(faces)


# ---------- clustering ----------

def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n else v


def _matrix():
    rows = people_repo.load_embeddings()
    ids, vecs, persons = [], [], []
    for r in rows:
        ids.append(r["id"])
        persons.append(r["person_id"])
        vecs.append(np.frombuffer(r["embedding"], dtype=np.float32))
    if not vecs:
        return [], np.zeros((0, 512)), []
    return ids, np.vstack(vecs), persons


def cluster_unassigned(eps: float = 0.45, min_samples: int = 2):
    ids, vecs, persons = _matrix()
    if not ids:
        return

    named_idx = [i for i, p in enumerate(persons) if p is not None]
    centroids = {}
    for pid in {persons[i] for i in named_idx}:
        idx = [i for i in named_idx if persons[i] == pid]
        centroids[pid] = _norm(vecs[idx].mean(axis=0))

    free = [i for i, p in enumerate(persons) if p is None]
    assigned: list[tuple[int, int]] = []
    for i in list(free):
        best_pid, best_sim = None, 0.0
        for pid, c in centroids.items():
            sim = float(np.dot(_norm(vecs[i]), c))
            if sim > best_sim:
                best_pid, best_sim = pid, sim
        if best_sim >= 0.55:
            assigned.append((best_pid, ids[i]))
    if assigned:
        people_repo.assign_faces(assigned)
        done = {fid for _, fid in assigned}
        free = [i for i in free if ids[i] not in done]
    if not free:
        return

    labels = _dbscan_cosine(vecs[free], eps, min_samples)
    for lbl in sorted(set(labels)):
        members = [ids[free[k]] for k in range(len(free)) if labels[k] == lbl]
        if lbl == -1 or len(members) < min_samples:
            people_repo.set_cluster(members, None)
            continue
        pid = people_repo.create(f"Person {datetime.now():%m%d}-{int(lbl) + 1}", auto=True)
        people_repo.assign_cluster(members, pid, int(lbl))
        people_repo.set_cover(pid, members[0])


def _dbscan_cosine(vecs, eps, min_samples):
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
        members = [j for j in range(n) if float(v[j] @ v[i]) >= sim_threshold]
        if len(members) >= min_samples:
            for j in members:
                if labels[j] == -1:
                    labels[j] = cur
            cur += 1
    return np.array(labels)


def crop_face(face_id: int):
    f = people_repo.face_with_photo(face_id)
    if not f:
        return None
    with Image.open(f["path"]) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        pad_x, pad_y = f["bbox_w"] // 4, f["bbox_h"] // 4
        box = (max(0, f["bbox_x"] - pad_x), max(0, f["bbox_y"] - pad_y),
               f["bbox_x"] + f["bbox_w"] + pad_x, f["bbox_y"] + f["bbox_h"] + pad_y)
        return im.crop(box)
