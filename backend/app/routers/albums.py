from fastapi import APIRouter

from ..schemas import AlbumCreate, AlbumOut, AlbumPhotos
from ..services import album_service

router = APIRouter(prefix="/api", tags=["albums"])


@router.get("/albums", response_model=list[AlbumOut])
def list_albums():
    return album_service.list_albums()


@router.post("/albums")
def create_album(body: AlbumCreate):
    return album_service.create(body.name)


@router.patch("/albums/{album_id}")
def rename_album(album_id: int, body: AlbumCreate):
    album_service.rename(album_id, body.name)
    return {"ok": True}


@router.delete("/albums/{album_id}")
def delete_album(album_id: int):
    album_service.delete(album_id)
    return {"ok": True}


@router.post("/albums/{album_id}/photos")
def add_to_album(album_id: int, body: AlbumPhotos):
    return album_service.add_photos(album_id, body.photo_ids)


@router.delete("/albums/{album_id}/photos")
def remove_from_album(album_id: int, body: AlbumPhotos):
    return album_service.remove_photos(album_id, body.photo_ids)


@router.put("/albums/{album_id}/cover/{photo_id}")
def set_cover(album_id: int, photo_id: int):
    album_service.set_cover(album_id, photo_id)
    return {"ok": True}
