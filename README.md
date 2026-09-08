# PhotoLibrary Viewer

A local web app to browse, search, organize and de-duplicate the photo & video
collection under `D:\PhotoLibrary`.

Everything runs on your machine. No photos leave your computer.

## Features

| Area | What it does |
|------|--------------|
| **Browse** | Fast thumbnail gallery of `D:\PhotoLibrary` and every sub-folder. |
| **Filter / sort** | By date range, location, camera, media type, person (face), duplicates. Sort by date / name / size. |
| **Find by face** | On-device face detection + clustering (InsightFace). Name a person once, then filter the whole library by them. Photo-level people tags work even without the face model. |
| **Lightbox** | Click a photo for a large view; click a video to play it (streamed with range requests). Keyboard: ← → navigate, `Esc` close. |
| **Import** | Pull photos/videos from any folder into `D:\PhotoLibrary` as `YYYY / YYYY-MM-DD / Location`. Uses EXIF date + GPS reverse-geocoding. Skips files already in the library. |
| **Convert** | Change format (JPG/PNG/WebP/HEIC→…), resize, keep or strip EXIF. In place or as a copy. |
| **Delete** | Sends files to the Windows Recycle Bin (recoverable). |
| **Duplicates** | Exact (SHA-256) and near-duplicate (perceptual hash) detection with a review/resolve screen and auto-resolve (keep best, bin the rest). |

## Layout

```
backend/    FastAPI + SQLite. Scans the library, stores metadata, serves media & thumbnails.
frontend/   React + Vite single-page app.
```

The backend is layered **routers → services → repositories → database**, with
Pydantic DTOs in `schemas.py` and domain errors in `core/`. See
[backend/ARCHITECTURE.md](backend/ARCHITECTURE.md).

## Setup

### Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py            # http://127.0.0.1:8077
```

Optional face recognition (large download, needs wheels for your Python):

```powershell
pip install -r requirements-faces.txt
```

Optional offline location names for import:

```powershell
pip install reverse_geocoder
```

### Frontend

```powershell
cd frontend
npm install
npm run dev             # http://127.0.0.1:5173  (proxies /api to the backend)
```

For a single-process deployment: `npm run build`, then the backend serves
`frontend/dist` at `http://127.0.0.1:8077`.

## First run

1. Start the backend, then the frontend, open http://127.0.0.1:5173.
2. **Settings → Rescan library** to index `D:\PhotoLibrary`.
3. (Optional) **People → Detect faces** to build face clusters.

The first scan hashes every file and builds a thumbnail, so it takes a while on a
large library — progress shows in the top bar, and photos appear as soon as it
finishes. It runs in parallel (tune **Settings → Scan workers**). Corrupt or
truncated files (common with interrupted phone transfers) are indexed anyway with
a placeholder thumbnail and listed under **Settings → last scan**, so you can find
and delete them.

## Debugging (VS Code)

`.vscode/` ships launch configs and tasks:

| Config | Use |
|--------|-----|
| **Backend: FastAPI (debug)** | Runs uvicorn under debugpy, no reload — breakpoints work everywhere. |
| **Backend: FastAPI (auto-reload …)** | `run.py` with `DEV=1`; reload on save, breakpoints only in the reloader process. |
| **Backend: current file** | Debug the open `.py` (e.g. poke at a service module directly). |
| **Backend: attach to running process** | Start the server yourself with `DEBUGPY=1 python run.py`, then attach on `:5678`. Add `DEBUGPY_WAIT=1` to pause until the debugger connects. |
| **Frontend: Chrome / Edge** | Launches the browser against the Vite dev server (auto-starts it) with source maps into `frontend/src`. |
| **Full stack (backend + Chrome)** | Compound — starts both. |

Install the debug tooling once: `pip install -r requirements-dev.txt` in the backend venv.

## Configuration

Environment variables (or edit `~/.imageviewer/settings.json`):

| Var | Default | Meaning |
|-----|---------|---------|
| `PHOTO_LIBRARY` | `D:\PhotoLibrary` | Root of the managed library. |
| `IMAGEVIEWER_DATA` | `~/.imageviewer` | Where the DB and thumbnail cache live. |
| `IMAGEVIEWER_PORT` | `8077` | Backend port. |
