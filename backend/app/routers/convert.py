from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import convert

router = APIRouter(prefix="/api", tags=["convert"])


class ConvertBody(BaseModel):
    target: str
    max_dimension: int | None = None
    quality: int = 90
    keep_exif: bool = True
    overwrite: bool = False


@router.post("/photos/{photo_id}/convert")
def convert_photo(photo_id: int, body: ConvertBody):
    try:
        return convert.convert_photo(
            photo_id, target=body.target, max_dimension=body.max_dimension,
            quality=body.quality, keep_exif=body.keep_exif, overwrite=body.overwrite,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
