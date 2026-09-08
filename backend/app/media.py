"""Serve original media files, with HTTP range support for video seeking."""
import mimetypes
import os
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

_CHUNK = 1024 * 1024


def file_response(path: str, request: Request, download: bool = False):
    p = Path(path)
    if not p.is_file():
        raise HTTPException(404, "file not found")

    media_type = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    file_size = p.stat().st_size
    disposition = "attachment" if download else "inline"
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'{disposition}; filename="{p.name}"',
    }

    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(p, media_type=media_type, headers=headers)

    try:
        units, _, rng = range_header.partition("=")
        start_s, _, end_s = rng.partition("-")
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else file_size - 1
    except ValueError:
        raise HTTPException(416, "invalid range")
    end = min(end, file_size - 1)
    if start > end:
        raise HTTPException(416, "range not satisfiable")

    length = end - start + 1

    def streamer():
        with open(p, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(_CHUNK, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers.update({
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(length),
    })
    return StreamingResponse(streamer(), status_code=206,
                             media_type=media_type, headers=headers)
