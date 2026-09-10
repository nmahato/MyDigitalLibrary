from fastapi import APIRouter

from ..schemas import (
    ConvertRequest, ConvertResult, EnhanceRequest, ResizeRequest, RotateRequest,
)
from ..services import conversion_service

router = APIRouter(prefix="/api", tags=["edit"])


@router.post("/photos/{photo_id}/convert", response_model=ConvertResult)
def convert_photo(photo_id: int, body: ConvertRequest):
    return conversion_service.convert(
        photo_id, target=body.target, max_dimension=body.max_dimension,
        quality=body.quality, keep_exif=body.keep_exif, overwrite=body.overwrite,
    )


@router.post("/photos/{photo_id}/rotate", response_model=ConvertResult)
def rotate_photo(photo_id: int, body: RotateRequest):
    return conversion_service.rotate(
        photo_id, degrees=body.degrees, overwrite=body.overwrite)


@router.post("/photos/{photo_id}/resize", response_model=ConvertResult)
def resize_photo(photo_id: int, body: ResizeRequest):
    return conversion_service.resize(
        photo_id, max_dimension=body.max_dimension, width=body.width,
        height=body.height, overwrite=body.overwrite)


@router.post("/photos/{photo_id}/enhance", response_model=ConvertResult)
def enhance_photo(photo_id: int, body: EnhanceRequest):
    return conversion_service.enhance(
        photo_id, auto=body.auto, brightness=body.brightness, contrast=body.contrast,
        color=body.color, sharpness=body.sharpness, overwrite=body.overwrite)
