"""Shared Pillow configuration. Import this before using PIL elsewhere."""
from PIL import ImageFile

# Real libraries contain half-written / truncated JPEGs; don't hard-fail on them.
ImageFile.LOAD_TRUNCATED_IMAGES = True

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except Exception:  # pragma: no cover
    pass
