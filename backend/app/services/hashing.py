"""Content hashing: exact (SHA-256) and perceptual (pHash), scipy-free."""
import hashlib

import numpy as np
from PIL import Image

from . import imaging  # noqa: F401  (configures Pillow)


def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _dct_1d(x: np.ndarray) -> np.ndarray:
    """Type-II DCT along the last axis, ortho-ish (constant scale is fine for hashing)."""
    n = x.shape[-1]
    v = np.empty_like(x)
    half = (n + 1) // 2
    v[..., :half] = x[..., ::2]
    v[..., half:] = x[..., 1::2][..., ::-1]
    V = np.fft.fft(v, axis=-1)
    k = np.arange(n)
    factor = 2 * np.exp(-1j * np.pi * k / (2 * n))
    return (V * factor).real


def phash(image: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    size = hash_size * highfreq_factor
    img = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = np.asarray(img, dtype=np.float64)
    d = _dct_1d(_dct_1d(pixels).T).T
    low = d[:hash_size, :hash_size]
    med = np.median(low)
    bits = (low > med).flatten()
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return f"{value:016x}"


def hamming(a: str, b: str) -> int:
    if not a or not b:
        return 64
    return bin(int(a, 16) ^ int(b, 16)).count("1")
