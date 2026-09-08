"""EXIF / metadata extraction for images and (via ffprobe) videos."""
import json
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image

from . import imaging  # noqa: F401  (configures Pillow: HEIC + truncated images)

_DT_TAGS = (36867, 36868, 306)  # DateTimeOriginal, DateTimeDigitized, DateTime


def _to_deg(value) -> float:
    d, m, s = value
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def _parse_dt(raw: str):
    raw = str(raw).strip().strip("\x00").strip()
    if not raw or raw.startswith("0000"):
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw[:19])
    except ValueError:
        return None


def extract_image(path: str) -> dict:
    out = {
        "width": None, "height": None, "orientation": 1,
        "taken_at": None, "camera_make": None, "camera_model": None,
        "gps_lat": None, "gps_lon": None,
    }
    with Image.open(path) as im:
        out["width"], out["height"] = im.size
        try:
            exif = im.getexif()
        except Exception:
            exif = None
        if not exif:
            return out

        out["orientation"] = int(exif.get(274, 1) or 1)
        out["camera_make"] = _clean(exif.get(271))
        out["camera_model"] = _clean(exif.get(272))

        ifd = {}
        try:
            ifd = exif.get_ifd(0x8769)  # ExifIFD
        except Exception:
            pass
        for tag in _DT_TAGS:
            raw = ifd.get(tag) or exif.get(tag)
            if raw:
                dt = _parse_dt(raw)
                if dt:
                    out["taken_at"] = dt.replace(microsecond=0).isoformat()
                    break

        try:
            gps = exif.get_ifd(0x8825)
        except Exception:
            gps = None
        if gps and 2 in gps and 4 in gps:
            try:
                lat = _to_deg(gps[2])
                lon = _to_deg(gps[4])
                if str(gps.get(1, "N")).upper().startswith("S"):
                    lat = -lat
                if str(gps.get(3, "E")).upper().startswith("W"):
                    lon = -lon
                out["gps_lat"], out["gps_lon"] = round(lat, 6), round(lon, 6)
            except Exception:
                pass
    return out


def _clean(v):
    if v is None:
        return None
    s = str(v).strip().strip("\x00").strip()
    return s or None


def extract_video(path: str) -> dict:
    out = {
        "width": None, "height": None, "orientation": 1, "duration_sec": None,
        "taken_at": None, "camera_make": None, "camera_model": None,
        "gps_lat": None, "gps_lon": None,
    }
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(proc.stdout or "{}")
    except Exception:
        return out

    for st in data.get("streams", []):
        if st.get("codec_type") == "video":
            out["width"] = st.get("width")
            out["height"] = st.get("height")
            if st.get("duration"):
                out["duration_sec"] = float(st["duration"])
            break

    fmt = data.get("format", {})
    if fmt.get("duration") and not out["duration_sec"]:
        out["duration_sec"] = float(fmt["duration"])
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    for key in ("creation_time", "date"):
        if key in tags:
            dt = _parse_dt(tags[key].replace("T", " ").replace("Z", ""))
            if dt:
                out["taken_at"] = dt.replace(microsecond=0).isoformat()
                break
    loc = tags.get("location") or tags.get("com.apple.quicktime.location.iso6709")
    if loc:
        try:
            import re

            nums = re.findall(r"[+-]\d+\.\d+", loc)
            if len(nums) >= 2:
                out["gps_lat"], out["gps_lon"] = float(nums[0]), float(nums[1])
        except Exception:
            pass
    return out


def date_from_filename(name: str):
    import re

    m = re.search(r"(20\d{2}|19\d{2})[-_.]?(\d{2})[-_.]?(\d{2})", name)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(y, mo, d).isoformat()
    except ValueError:
        return None
