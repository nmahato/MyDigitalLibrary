"""Image editing: format conversion, resize, rotate, enhance. Writes to disk."""
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from ..core import BadRequest, NotFound
from ..repositories import photos as photo_repo
from . import imaging  # noqa: F401
from .hashing import phash, sha256_file
from .thumbnails import ensure_thumb

_FORMATS = {
    "jpg": ("JPEG", ".jpg"), "jpeg": ("JPEG", ".jpg"),
    "png": ("PNG", ".png"), "webp": ("WEBP", ".webp"),
    "tiff": ("TIFF", ".tiff"), "heic": ("HEIF", ".heic"),
}
_PIL_FMT_BY_EXT = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP",
    ".tif": "TIFF", ".tiff": "TIFF", ".heic": "HEIF", ".heif": "HEIF",
    ".bmp": "BMP", ".gif": "GIF",
}


def _require_image(photo_id: int):
    row = photo_repo.get(photo_id)
    if not row:
        raise NotFound("photo not found")
    if row["media_type"] != "image":
        raise BadRequest("only images can be edited")
    return row


def _free_name(path: Path, tag: str) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem}-{tag}{'' if i == 1 else i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def _write(row, im: Image.Image, *, overwrite: bool, tag: str,
           pil_fmt: str | None = None, ext: str | None = None,
           quality: int = 92, exif_bytes: bytes | None = None) -> dict:
    """Save `im`, update the DB row + thumbnail when overwriting."""
    src = Path(row["path"])
    ext = ext or src.suffix.lower()
    pil_fmt = pil_fmt or _PIL_FMT_BY_EXT.get(ext, "PNG")
    if pil_fmt in ("JPEG", "HEIF") and im.mode in ("RGBA", "P", "LA"):
        im = im.convert("RGB")

    dst = src.with_suffix(ext) if overwrite else _free_name(src.with_suffix(ext), tag)
    kwargs: dict = {}
    if pil_fmt in ("JPEG", "WEBP", "HEIF"):
        kwargs["quality"] = quality
    if exif_bytes:
        kwargs["exif"] = exif_bytes
    im.save(dst, pil_fmt, **kwargs)

    if overwrite and dst != src and src.exists():
        src.unlink()

    st = dst.stat()
    with Image.open(dst) as reopened:
        ph = phash(reopened)
        w, h = reopened.size

    new_id = None
    if overwrite:
        photo_repo.apply_conversion(row["id"], {
            "path": str(dst), "filename": dst.name, "ext": ext.lstrip("."),
            "size_bytes": st.st_size, "width": w, "height": h,
            "sha256": sha256_file(str(dst)), "phash": ph, "orientation": 1,
            "indexed_at": datetime.now().isoformat(),
        })
        ensure_thumb(row["id"], str(dst), "image", force=True)
        new_id = row["id"]

    return {"output": str(dst), "size_bytes": st.st_size, "width": w, "height": h,
            "photo_id": new_id, "replaced": overwrite}


# ---------------------------------------------------------------- convert

def convert(photo_id: int, *, target: str, max_dimension: int | None = None,
            quality: int = 90, keep_exif: bool = True,
            overwrite: bool = False) -> dict:
    target = target.lower()
    if target not in _FORMATS:
        raise BadRequest(f"unsupported target format: {target}")
    pil_fmt, ext = _FORMATS[target]
    row = _require_image(photo_id)

    with Image.open(row["path"]) as im:
        im = ImageOps.exif_transpose(im)
        exif_bytes = im.info.get("exif") if keep_exif else None
        if max_dimension:
            im.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        return _write(row, im, overwrite=overwrite, tag="conv", pil_fmt=pil_fmt,
                      ext=ext, quality=quality, exif_bytes=exif_bytes)


# ---------------------------------------------------------------- rotate

def rotate(photo_id: int, *, degrees: int, overwrite: bool = True) -> dict:
    deg = degrees % 360
    if deg not in (90, 180, 270):
        raise BadRequest("degrees must be 90, 180 or 270")
    row = _require_image(photo_id)
    ops = {
        90: Image.Transpose.ROTATE_270,   # PIL rotates CCW; 90 CW = ROTATE_270
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }
    with Image.open(row["path"]) as im:
        im = ImageOps.exif_transpose(im).transpose(ops[deg])
        return _write(row, im, overwrite=overwrite, tag="rot")


# ---------------------------------------------------------------- resize

def resize(photo_id: int, *, max_dimension: int | None = None,
           width: int | None = None, height: int | None = None,
           overwrite: bool = True) -> dict:
    row = _require_image(photo_id)
    with Image.open(row["path"]) as im:
        im = ImageOps.exif_transpose(im)
        if max_dimension:
            im.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        elif width or height:
            w0, h0 = im.size
            if width and height:
                target = (width, height)
            elif width:
                target = (width, max(1, round(h0 * width / w0)))
            else:
                target = (max(1, round(w0 * height / h0)), height)
            im = im.resize(target, Image.Resampling.LANCZOS)
        else:
            raise BadRequest("give max_dimension, or width and/or height")
        return _write(row, im, overwrite=overwrite, tag="resized")


# ---------------------------------------------------------------- enhance

def enhance(photo_id: int, *, auto: bool = True, brightness: float = 1.0,
            contrast: float = 1.0, color: float = 1.0, sharpness: float = 1.0,
            overwrite: bool = True) -> dict:
    row = _require_image(photo_id)
    with Image.open(row["path"]) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "RGBA", "L"):
            im = im.convert("RGB")
        if auto:
            base = im.convert("RGB") if im.mode == "RGBA" else im
            im = ImageOps.autocontrast(base, cutoff=1)
        for factor, enhancer in (
            (brightness, ImageEnhance.Brightness),
            (contrast, ImageEnhance.Contrast),
            (color, ImageEnhance.Color),
            (sharpness, ImageEnhance.Sharpness),
        ):
            if abs(factor - 1.0) > 1e-3:
                try:
                    im = enhancer(im).enhance(factor)
                except ValueError:
                    pass  # e.g. Color on an L image
        return _write(row, im, overwrite=overwrite, tag="enhanced")
