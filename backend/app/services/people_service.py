"""Business logic for people, face assignments and photo tags."""
from ..core import BadRequest, DependencyMissing, NotFound
from ..repositories import people as people_repo
from ..repositories import photos as photo_repo
from . import face_engine


def list_people() -> list[dict]:
    return [dict(r) for r in people_repo.list_with_counts()]


def create(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise BadRequest("name is required")
    existing = people_repo.find_by_name(name)
    if existing:
        return dict(existing)
    pid = people_repo.create(name)
    _recognize_async()
    return {"id": pid, "name": name}


def rename(person_id: int, name: str) -> None:
    person = people_repo.get(person_id)
    if not person:
        raise NotFound("person not found")
    if not (name or "").strip():
        raise BadRequest("name is required")
    was_auto = bool(person["auto"])
    people_repo.rename(person_id, name)   # also flips auto -> 0
    if was_auto:
        # naming an auto group vouches for its members
        people_repo.confirm_person_faces(person_id)
    _recognize_async()


def delete(person_id: int) -> None:
    people_repo.delete(person_id)


def merge(source_id: int, target_id: int) -> None:
    if source_id == target_id:
        raise BadRequest("cannot merge a person into themselves")
    if not people_repo.get(source_id) or not people_repo.get(target_id):
        raise NotFound("person not found")
    people_repo.merge(source_id, target_id)


def faces_of(person_id: int, status: str = "all") -> list[dict]:
    return [dict(r) for r in people_repo.faces_for_person(person_id, status=status)]


def face_crop(face_id: int):
    img = face_engine.crop_face(face_id)
    if img is None:
        raise NotFound("face not found")
    return img


def assign_face(face_id: int, *, person_id: int | None, name: str | None) -> dict:
    face = people_repo.get_face(face_id)
    if not face:
        raise NotFound("face not found")
    if person_id is None and name:
        person = people_repo.find_by_name(name)
        person_id = person["id"] if person else people_repo.create(name.strip())
    people_repo.assign_face(face_id, person_id, confirmed=person_id is not None)
    if person_id and not people_repo.get(person_id)["cover_face"]:
        people_repo.set_cover(person_id, face_id)
    people_repo.delete_empty_auto_people()
    _recognize_async()
    return {"ok": True, "person_id": person_id}


def confirm_face(face_id: int) -> dict:
    face = people_repo.get_face(face_id)
    if not face:
        raise NotFound("face not found")
    if not face["person_id"]:
        raise BadRequest("face is not assigned to anyone")
    people_repo.confirm_face(face_id)
    if not people_repo.get(face["person_id"])["cover_face"]:
        people_repo.set_cover(face["person_id"], face_id)
    return {"ok": True}


def detach_face(face_id: int) -> dict:
    if not people_repo.get_face(face_id):
        raise NotFound("face not found")
    people_repo.detach_face(face_id)
    people_repo.delete_empty_auto_people()
    return {"ok": True}


def tag_photo(photo_id: int, person_id: int) -> None:
    if not photo_repo.get(photo_id):
        raise NotFound("photo not found")
    if not people_repo.get(person_id):
        raise NotFound("person not found")
    people_repo.add_tag(photo_id, person_id)


def untag_photo(photo_id: int, person_id: int) -> None:
    people_repo.remove_tag(photo_id, person_id)


# ---------- face engine control ----------

def engine_status() -> dict:
    return face_engine.status()


def _require_engine():
    if not face_engine.available():
        raise DependencyMissing(
            "face engine not installed - pip install -r requirements-faces.txt")


def _recognize_async():
    """Best-effort re-recognition after the people set changes."""
    if face_engine.available() and not face_engine.running():
        import threading

        threading.Thread(target=face_engine.recognize, daemon=True).start()


def detect(limit: int | None) -> dict:
    _require_engine()
    if face_engine.running():
        return {"started": False, "reason": "already running"}
    face_engine.start_detection(limit)
    return {"started": True}


def recognize() -> dict:
    _require_engine()
    matched = face_engine.recognize()
    face_engine.cluster_unassigned()
    return {"suggested": matched}


def recluster() -> None:
    _require_engine()
    face_engine.cluster_unassigned()
