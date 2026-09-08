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
    return {"id": pid, "name": name}


def rename(person_id: int, name: str) -> None:
    if not people_repo.get(person_id):
        raise NotFound("person not found")
    if not (name or "").strip():
        raise BadRequest("name is required")
    people_repo.rename(person_id, name)


def delete(person_id: int) -> None:
    people_repo.delete(person_id)


def merge(source_id: int, target_id: int) -> None:
    if source_id == target_id:
        raise BadRequest("cannot merge a person into themselves")
    if not people_repo.get(source_id) or not people_repo.get(target_id):
        raise NotFound("person not found")
    people_repo.merge(source_id, target_id)


def faces_of(person_id: int) -> list[dict]:
    return [dict(r) for r in people_repo.faces_for_person(person_id)]


def face_crop(face_id: int):
    img = face_engine.crop_face(face_id)
    if img is None:
        raise NotFound("face not found")
    return img


def assign_face(face_id: int, *, person_id: int | None, name: str | None) -> dict:
    if person_id is None and name:
        person = people_repo.find_by_name(name)
        person_id = person["id"] if person else people_repo.create(name.strip())
    people_repo.assign_face(face_id, person_id)
    return {"ok": True, "person_id": person_id}


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


def detect(limit: int | None) -> dict:
    if not face_engine.available():
        raise DependencyMissing(
            "face engine not installed - pip install -r requirements-faces.txt")
    if face_engine.running():
        return {"started": False, "reason": "already running"}
    face_engine.start_detection(limit)
    return {"started": True}


def recluster() -> None:
    face_engine.cluster_unassigned()
