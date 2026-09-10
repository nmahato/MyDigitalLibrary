from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from ..core import NotFound
from ..media import file_response
from ..schemas import (
    DeleteRequest, DeleteResult, Facets, PhotoDetail, PhotoFilters, PhotoPage,
    RatingRequest,
)
from ..services import photo_service
from ..services.thumbnails import ensure_thumb

router = APIRouter(prefix="/api", tags=["photos"])


def filter_params(
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    media_type: str | None = None,
    location: str | None = None,
    camera: str | None = None,
    person_id: int | None = None,
    album_id: int | None = None,
    tag: str | None = None,
    year: int | None = None,
    folder: str | None = None,
    duplicates_only: bool = False,
    sort: str = "date",
    order: str = "desc",
    limit: int = Query(120, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PhotoFilters:
    return PhotoFilters(
        q=q, date_from=date_from, date_to=date_to, media_type=media_type,
        location=location, camera=camera, person_id=person_id, album_id=album_id,
        tag=tag, year=year, folder=folder, duplicates_only=duplicates_only,
        sort=sort, order=order, limit=limit, offset=offset,
    )


@router.get("/photos", response_model=PhotoPage)
def list_photos(filters: PhotoFilters = Depends(filter_params)):
    return photo_service.search(filters)


@router.get("/photos/facets", response_model=Facets)
def facets():
    return photo_service.facets()


@router.get("/photos/{photo_id}", response_model=PhotoDetail)
def get_photo(photo_id: int):
    return photo_service.get_detail(photo_id)


@router.get("/photos/{photo_id}/thumb")
def photo_thumb(photo_id: int):
    path, media_type = photo_service.require_path(photo_id)
    thumb = ensure_thumb(photo_id, path, media_type)
    if not thumb:
        raise NotFound("no thumbnail")
    return FileResponse(thumb, media_type="image/webp")


@router.get("/photos/{photo_id}/file")
def photo_file(photo_id: int, request: Request):
    path, _ = photo_service.require_path(photo_id)
    return file_response(path, request)


@router.get("/photos/{photo_id}/download")
def photo_download(photo_id: int, request: Request):
    path, _ = photo_service.require_path(photo_id)
    return file_response(path, request, download=True)


@router.post("/photos/delete", response_model=DeleteResult)
def delete_photos(body: DeleteRequest):
    return photo_service.delete(body.ids)


@router.patch("/photos/{photo_id}/rating")
def set_rating(photo_id: int, body: RatingRequest):
    photo_service.set_rating(photo_id, body.rating)
    return {"ok": True}
