from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core import install_error_handlers
from .database import init_db
from .routers import (
    albums, convert, duplicates, imports, library, people, photos, tags,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="PhotoLibrary Viewer", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

install_error_handlers(app)

for module in (photos, library, people, albums, tags, duplicates, imports, convert):
    app.include_router(module.router)


@app.get("/api/health")
def health():
    return {"ok": True}


_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/")
    def _index():
        return FileResponse(_DIST / "index.html")

    @app.get("/{full_path:path}")
    def _spa(full_path: str):
        target = _DIST / full_path
        return FileResponse(target if target.is_file() else _DIST / "index.html")
