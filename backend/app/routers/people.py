import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..schemas import (
    DetectRequest, FaceAssign, FaceEngineStatus, MergeRequest, PersonCreate,
    PersonOut, TagRequest,
)
from ..services import people_service

router = APIRouter(prefix="/api", tags=["people"])


@router.get("/people", response_model=list[PersonOut])
def list_people():
    return people_service.list_people()


@router.post("/people")
def create_person(body: PersonCreate):
    return people_service.create(body.name)


@router.patch("/people/{person_id}")
def rename_person(person_id: int, body: PersonCreate):
    people_service.rename(person_id, body.name)
    return {"ok": True}


@router.delete("/people/{person_id}")
def delete_person(person_id: int):
    people_service.delete(person_id)
    return {"ok": True}


@router.post("/people/merge")
def merge_people(body: MergeRequest):
    people_service.merge(body.source_id, body.target_id)
    return {"ok": True}


@router.get("/people/{person_id}/faces")
def person_faces(person_id: int):
    return people_service.faces_of(person_id)


@router.get("/faces/{face_id}/crop")
def face_crop(face_id: int):
    img = people_service.face_crop(face_id)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


@router.post("/faces/{face_id}/assign")
def assign_face(face_id: int, body: FaceAssign):
    return people_service.assign_face(face_id, person_id=body.person_id, name=body.name)


@router.get("/faces/status", response_model=FaceEngineStatus)
def faces_status():
    return people_service.engine_status()


@router.post("/faces/detect")
def detect(body: DetectRequest):
    return people_service.detect(body.limit)


@router.post("/faces/cluster")
def recluster():
    people_service.recluster()
    return {"ok": True}


@router.post("/photos/{photo_id}/people")
def tag_photo(photo_id: int, body: TagRequest):
    people_service.tag_photo(photo_id, body.person_id)
    return {"ok": True}


@router.delete("/photos/{photo_id}/people/{person_id}")
def untag_photo(photo_id: int, person_id: int):
    people_service.untag_photo(photo_id, person_id)
    return {"ok": True}
