from fastapi import APIRouter

from ..schemas import ConvertRequest, ConvertResult
from ..services import conversion_service

router = APIRouter(prefix="/api", tags=["convert"])


@router.post("/photos/{photo_id}/convert", response_model=ConvertResult)
def convert_photo(photo_id: int, body: ConvertRequest):
    return conversion_service.convert(
        photo_id, target=body.target, max_dimension=body.max_dimension,
        quality=body.quality, keep_exif=body.keep_exif, overwrite=body.overwrite,
    )
