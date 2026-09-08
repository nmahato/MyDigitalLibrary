from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import convert, duplicates, imports, library, people, photos

app = FastAPI(title="PhotoLibrary Viewer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photos.router)
app.include_router(library.router)
app.include_router(people.router)
app.include_router(duplicates.router)
app.include_router(imports.router)
app.include_router(convert.router)


@app.on_event("startup")
def _startup():
    init_db()


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
        if target.is_file():
            return FileResponse(target)
        return FileResponse(_DIST / "index.html")
