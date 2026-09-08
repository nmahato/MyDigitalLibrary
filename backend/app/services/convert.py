"""Image format conversion / resizing."""
from pathlib import Path

from PIL import Image, ImageOps

from ..database import get_conn
from . import imaging  # noqa: F401  (configures Pillow)
from .hashing import phash, sha256_file
from .thumbnails import ensure_thumb

_FORMATS = {
    "jpg": ("JPEG", ".jpg"), "jpeg": ("JPEG", ".jpg"),
    "png": ("PNG", ".png"), "webp": ("WEBP", ".webp"),
    "tiff": ("TIFF", ".tiff"), "heic": ("HEIF", ".heic"),
}


def convert_photo(photo_id: int, *, target: str, max_dimension: int | None = None,
                  quality: int = 90, keep_exif: bool = True,
                  overwrite: bool = False) -> dict:
    target = target.lower()
    if target not in _FORMATS:
        raise ValueError(f"unsupported target format: {target}")
    pil_fmt, ext = _FORMATS[target]

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM photos WHERE id=?", (photo_id,)).fetchone()
    if not row:
        raise ValueError("photo not found")
    if row["media_type"] != "image":
        raise ValueError("only images can be converted")

    src = Path(row["path"])
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        exif_bytes = im.info.get("exif") if keep_exif else None
        if max_dimension:
            im.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        if pil_fmt in ("JPEG", "HEIF") and im.mode in ("RGBA", "P", "LA"):
            im = im.convert("RGB")

        dst = src.with_suffix(ext) if overwrite else _free_name(src.with_suffix(ext))
        save_kwargs = {}
        if pil_fmt in ("JPEG", "WEBP", "HEIF"):
            save_kwargs["quality"] = quality
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
        im.save(dst, pil_fmt, **save_kwargs)

    if overwrite and dst != src and src.exists():
        src.unlink()

    st = dst.stat()
    with Image.open(dst) as im2:
        ph = phash(im2)
        w, h = im2.size
    sha = sha256_file(str(dst))

    from datetime import datetime
    with get_conn() as conn:
        if overwrite:
            conn.execute(
                """UPDATE photos SET path=?, filename=?, ext=?, size_bytes=?,
                   width=?, height=?, sha256=?, phash=?, orientation=1, indexed_at=?
                   WHERE id=?""",
                (str(dst), dst.name, ext.lstrip("."), st.st_size, w, h, sha, ph,
                 datetime.now().isoformat(), photo_id),
            )
            ensure_thumb(photo_id, str(dst), "image", force=True)
            new_id = photo_id
        else:
            new_id = None  # picked up on next rescan

    return {"output": str(dst), "size_bytes": st.st_size, "photo_id": new_id,
            "replaced": overwrite}


def _free_name(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        cand = path.with_name(f"{path.stem}-conv{'' if i == 1 else i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1
