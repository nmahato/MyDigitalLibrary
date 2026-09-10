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

        PROGRESS["phase"] = "recognising"
        recognize()
        PROGRESS["phase"] = "grouping"
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


# ---------- recognition + clustering ----------

RECOGNIZE_THRESHOLD = 0.42   # cosine to a named person's centroid -> suggestion
CLUSTER_MATCH_THRESHOLD = 0.45


def _norm(v):
    n = np.linalg.norm(v)
    return v / n if n else v


def _buf(b):
    return np.frombuffer(b, dtype=np.float32)


def _centroids(*, auto: bool | None, confirmed_only: bool) -> dict[int, np.ndarray]:
    """Unit-normalised mean embedding per person, filtered by the `auto` flag."""
    groups: dict[int, list[np.ndarray]] = {}
    for r in people_repo.person_embeddings(confirmed_only=confirmed_only):
        if auto is not None and bool(r["auto"]) != auto:
            continue
        groups.setdefault(r["person_id"], []).append(_buf(r["embedding"]))
    return {pid: _norm(np.mean(v, axis=0)) for pid, v in groups.items() if v}


def recognize(threshold: float = RECOGNIZE_THRESHOLD) -> int:
    """Attach unassigned faces to the nearest *named* person as a suggestion."""
    centroids = _centroids(auto=False, confirmed_only=True)
    if not centroids:
        centroids = _centroids(auto=False, confirmed_only=False)
    if not centroids:
        return 0

    pids = list(centroids)
    mat = np.vstack([centroids[p] for p in pids])  # (P, D)

    rows = people_repo.unassigned_embeddings()
    updates: list[tuple[int, float, int]] = []
    for r in rows:
        v = _norm(_buf(r["embedding"]))
        sims = mat @ v
        j = int(np.argmax(sims))
        if float(sims[j]) >= threshold:
            updates.append((pids[j], round(float(sims[j]), 4), r["id"]))
    if updates:
        people_repo.apply_recognition(updates)
    return len(updates)


def cluster_unassigned(eps: float = 0.45, min_samples: int = 2):
    rows = people_repo.unassigned_embeddings()
    if len(rows) < min_samples:
        people_repo.delete_empty_auto_people()
        return

    ids = [r["id"] for r in rows]
    vecs = np.vstack([_buf(r["embedding"]) for r in rows])
    labels = _dbscan_cosine(vecs, eps, min_samples)

    auto_centroids = _centroids(auto=True, confirmed_only=False)
    auto_pids = list(auto_centroids)
    auto_mat = np.vstack([auto_centroids[p] for p in auto_pids]) if auto_pids else None
    seq = people_repo.count_auto_people()

    for lbl in sorted(set(labels)):
        members = [ids[k] for k in range(len(ids)) if labels[k] == lbl]
        if lbl == -1 or len(members) < min_samples:
            continue
        idx = [k for k in range(len(ids)) if labels[k] == lbl]
        centroid = _norm(vecs[idx].mean(axis=0))

        pid = None
        if auto_mat is not None:
            sims = auto_mat @ centroid
            j = int(np.argmax(sims))
            if float(sims[j]) >= CLUSTER_MATCH_THRESHOLD:
                pid = auto_pids[j]
        if pid is None:
            seq += 1
            pid = people_repo.create(f"Unnamed {seq}", auto=True)
            people_repo.set_cover(pid, members[0])
        people_repo.assign_cluster(members, pid, int(lbl))

    people_repo.delete_empty_auto_people()


def full_pass():
    recognize()
    cluster_unassigned()


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
