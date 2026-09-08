"""Reverse geocoding -> a short 'City, Country' label. Fully optional / cached."""
import time
import urllib.parse
import urllib.request

from ..config import load_settings
from ..repositories import geocode as geo_repo

_rg = None
_rg_tried = False


def _offline_lookup(lat: float, lon: float):
    global _rg, _rg_tried
    if not _rg_tried:
        _rg_tried = True
        try:
            import reverse_geocoder

            _rg = reverse_geocoder
        except Exception:
            _rg = None
    if _rg is None:
        return None
    try:
        res = _rg.search((lat, lon), mode=1)[0]
        city = res.get("name") or ""
        cc = res.get("cc") or ""
        return ", ".join(p for p in (city, cc) if p) or None
    except Exception:
        return None


def _nominatim_lookup(lat: float, lon: float, email: str):
    params = urllib.parse.urlencode({
        "lat": lat, "lon": lon, "format": "jsonv2", "zoom": "10", "email": email or "",
    })
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/reverse?{params}",
        headers={"User-Agent": "PhotoLibraryViewer/1.0"},
    )
    try:
        import json

        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        a = data.get("address", {})
        city = a.get("city") or a.get("town") or a.get("village") or a.get("county")
        country = a.get("country")
        time.sleep(1)  # be polite to the public endpoint
        return ", ".join(p for p in (city, country) if p) or data.get("display_name")
    except Exception:
        return None


def label_for(lat, lon):
    if lat is None or lon is None:
        return None
    settings = load_settings()
    mode = settings.get("geocode", "offline")
    if mode == "off":
        return None

    key = f"{round(lat, 3)},{round(lon, 3)}"
    cached = geo_repo.get_cached(key)
    if cached is not None:
        return cached

    label = None
    if mode == "nominatim":
        label = _nominatim_lookup(lat, lon, settings.get("nominatim_email", ""))
    if label is None:
        label = _offline_lookup(lat, lon)

    geo_repo.put_cached(key, label)
    return label
