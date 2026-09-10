"""Generate the PhotoLibrary Viewer design document (.docx)."""
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Pt, RGBColor

OUT = Path(r"C:\Personal\projects\ImageViewer\docs\PhotoLibrary-Design.docx")
OUT.parent.mkdir(parents=True, exist_ok=True)

doc = Document()

# ------------------------------------------------------------------ base styles
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)

for lvl, sz in ((1, 16), (2, 13), (3, 11.5)):
    st = doc.styles[f"Heading {lvl}"]
    st.font.name = "Calibri"
    st.font.size = Pt(sz)
    st.font.color.rgb = RGBColor(0x1F, 0x33, 0x55)

ACCENT = RGBColor(0x2D, 0x5F, 0xB3)


def h(text, level=1):
    doc.add_heading(text, level=level)


def p(text="", *, italic=False, bold=False, size=None):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.italic = italic
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    return para


def bullet(text, level=0):
    para = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    para.add_run(text)
    return para


def code(text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    return para


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, htext in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(htext)
        run.bold = True
        run.font.size = Pt(9.5)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(val))
            run.font.size = Pt(9)
    return t


# ------------------------------------------------------------------ title page
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("PhotoLibrary Viewer")
r.bold = True
r.font.size = Pt(30)
r.font.color.rgb = ACCENT

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run("Design Document")
r.font.size = Pt(16)

meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run(
    f"Version 1.0  \u2022  {date.today():%d %B %Y}  \u2022  Status: Implemented"
).font.size = Pt(10)

doc.add_paragraph()
lead = doc.add_paragraph()
lead.alignment = WD_ALIGN_PARAGRAPH.CENTER
lr = lead.add_run(
    "A self-hosted web application for browsing, organising, editing and "
    "de-duplicating a large local photo and video library, with on-device "
    "face recognition. All data stays on the machine."
)
lr.italic = True
lr.font.size = Pt(11)

doc.add_page_break()

# ------------------------------------------------------------------ TOC-ish
h("Contents", 1)
for n in [
    "1  Introduction", "2  System Overview", "3  Architecture", "4  Data Model",
    "5  Functional Design", "6  API Reference", "7  Key Design Decisions",
    "8  Deployment & Operations", "9  Security & Privacy",
    "10  Performance", "11  Limitations & Future Work", "Appendix A  Configuration",
]:
    doc.add_paragraph(n, style="List Number" if n[0].isdigit() else "Normal")
doc.add_page_break()

# ================================================================ 1 Introduction
h("1  Introduction", 1)

h("1.1  Purpose", 2)
p("This document describes the design of PhotoLibrary Viewer, an application that "
  "indexes the media collection under a single library folder (by default "
  "D:\\PhotoLibrary) and presents it through a browser UI for browsing, search, "
  "editing, tagging, album curation, face recognition, duplicate clean-up and "
  "structured import.")

h("1.2  Goals", 2)
for g in [
    "Handle a large library (100k+ items, ~600 GB) with a responsive UI.",
    "Keep every photo, video and derived datum on the local machine \u2014 no cloud services.",
    "Make the library searchable along many axes: date, folder, place, camera, "
    "person, album, hashtag, media type, duplicates.",
    "Provide non-destructive-by-default editing (rotate, resize, enhance, convert) "
    "with an explicit \u201creplace original\u201d opt-in.",
    "Recognise recurring people on-device and let the user correct the model with "
    "minimal clicks.",
    "Run as a normal local service (IIS) that starts with the machine.",
]:
    bullet(g)

h("1.3  Non-Goals", 2)
for g in [
    "Multi-user accounts, sharing or permissions.",
    "Remote / internet access (the app binds to localhost).",
    "Editing video, or RAW developing.",
    "Being a general-purpose DAM with custom metadata schemas.",
]:
    bullet(g)

# ================================================================ 2 Overview
h("2  System Overview", 1)
p("The system is a single IIS site. IIS (via the HttpPlatformHandler module) "
  "launches one Uvicorn process running the FastAPI backend and reverse-proxies "
  "every request to it. FastAPI serves the JSON API under /api and the built "
  "React single-page app for everything else. Metadata lives in a SQLite "
  "database; thumbnails and the face model live beside it.")

h("2.1  Technology Stack", 2)
table(
    ["Layer", "Technology"],
    [
        ["Backend", "Python 3.14, FastAPI, Uvicorn (single worker)"],
        ["Persistence", "SQLite (WAL mode), raw sqlite3 \u2014 no ORM"],
        ["Imaging", "Pillow (+ pillow-heif), ffmpeg / ffprobe for video"],
        ["Perceptual hash", "Custom scipy-free DCT (NumPy FFT)"],
        ["Face recognition", "InsightFace (buffalo_l), ONNX Runtime, scikit-learn (DBSCAN)"],
        ["Reverse geocoding", "reverse_geocoder (offline) or Nominatim (opt-in)"],
        ["Frontend", "React 18 + Vite, hand-rolled CSS (dark theme)"],
        ["Hosting", "IIS + HttpPlatformHandler on Windows"],
    ],
)

h("2.2  Request Flow", 2)
code("browser  \u2192  IIS :9090  \u2192  HttpPlatformHandler  \u2192  python run.py  \u2192  uvicorn  \u2192  app.main:app\n"
     "                                                                       \u251c\u2500 /api/*         FastAPI routers\n"
     "                                                                       \u2514\u2500 / , /assets/*  frontend/dist")

# ================================================================ 3 Architecture
h("3  Architecture", 1)

h("3.1  Backend Layering", 2)
p("Each layer depends only on the one below it. Services never import FastAPI; "
  "repositories hold every SQL statement.")
table(
    ["Layer", "Responsibility", "Location"],
    [
        ["Routers", "HTTP parsing, response shaping, response_model", "app/routers/"],
        ["Services", "Business logic, orchestration, domain errors", "app/services/*_service.py"],
        ["Repositories", "All SQL; returns rows / plain values", "app/repositories/"],
        ["Database", "Connection factory, schema, migrations", "app/database.py"],
        ["Schemas", "Pydantic request/response DTOs", "app/schemas.py"],
        ["Core", "Error types + HTTP mapping, Recycle-Bin deletion", "app/core/"],
    ],
)
p("Processing modules in app/services/ (exif, hashing, thumbnails, imaging, "
  "geocoding, indexer, face_engine) perform pure media / ML work and may use "
  "repositories but hold no HTTP concerns.")

h("3.2  Domain Services", 2)
table(
    ["Service", "Responsibility"],
    [
        ["library_service", "Parallel scan loop + progress, library status, settings"],
        ["photo_service", "Search / filter, detail, delete, rating, facets"],
        ["people_service", "People CRUD, merge, face assignment, recognition control, tags"],
        ["album_service", "Named photo collections"],
        ["tag_service", "Hashtags (normalisation, bulk apply, orphan cleanup)"],
        ["duplicate_service", "Union-find grouping, resolve / auto-resolve / ignore"],
        ["import_service", "Plan + run import into YYYY/YYYY-MM-DD/Location"],
        ["conversion_service", "Rotate, resize, enhance, format conversion"],
    ],
)

h("3.3  Error Handling", 2)
p("A service raises NotFound / BadRequest / Conflict / DependencyMissing "
  "(app.core.errors). install_error_handlers(app) turns any AppError into "
  "{\"detail\": \u2026, \"code\": \u2026} with the matching status code. Routers contain no "
  "try/except for domain failures.")

h("3.4  Frontend Structure", 2)
table(
    ["Component", "Role"],
    [
        ["App", "Tab shell (Library / People / Albums / Duplicates / Import / Settings), toast, status polling"],
        ["Gallery + FilterBar", "Virtualised grid, filter sidebar, multi-select bulk actions"],
        ["FolderTree", "Collapsible folder hierarchy with counts; show/hide toggle"],
        ["Lightbox", "Full view, video playback, metadata, chips, FaceOverlay"],
        ["FaceOverlay", "Face boxes drawn on the image; click to name / confirm / detach"],
        ["ImageEditor", "Resizable modal: rotate / resize / enhance / convert / delete"],
        ["PeoplePanel", "Named people, unnamed groups, confirmed / to-review tabs"],
        ["AlbumsPanel, DuplicatesView, ImportWizard, SettingsPanel", "Feature screens"],
    ],
)

# ================================================================ 4 Data Model
h("4  Data Model", 1)
p("SQLite, WAL mode. Additive column migrations run at startup for databases "
  "created by an earlier version.")

h("4.1  Tables", 2)
table(
    ["Table", "Purpose", "Key columns"],
    [
        ["photos", "One row per media file", "path (unique), rel_path, media_type, size_bytes, "
         "width, height, duration_sec, taken_at, date_source, camera_*, gps_lat/lon, "
         "location, orientation, sha256, phash, rating, faces_done"],
        ["people", "Named person or auto face group", "name, auto (1=unnamed group), cover_face"],
        ["faces", "One detected face", "photo_id, person_id, bbox_x/y/w/h, det_score, "
         "embedding (512-d f32 BLOB), cluster_id, confirmed, similarity"],
        ["photo_people", "Photo-level people tags (no model needed)", "photo_id, person_id"],
        ["albums / album_photos", "Named collections", "name, cover_photo / (album_id, photo_id)"],
        ["tags / photo_tags", "Hashtags", "name (unique, normalised) / (photo_id, tag_id)"],
        ["dup_ignored", "\u201cnot a duplicate\u201d pairs", "(a, b)"],
        ["geocode_cache", "Rounded lat/lon \u2192 label", "key, label"],
    ],
)

h("4.2  Face States", 2)
table(
    ["person_id", "confirmed", "Meaning"],
    [
        ["NULL", "\u2013", "Detected but not grouped or recognised (\u201cloose\u201d)"],
        ["set", "0", "Suggestion \u2014 from clustering or recognition; awaiting review"],
        ["set", "1", "Confirmed by the user"],
    ],
)

# ================================================================ 5 Functional
h("5  Functional Design", 1)

h("5.1  Library Scanning & Indexing", 2)
p("library_service walks the library with a ThreadPoolExecutor (worker count is "
  "configurable). For each media file the indexer extracts EXIF (date, GPS, "
  "camera, orientation), computes SHA-256 and a perceptual hash, reverse-geocodes "
  "GPS, and generates a 512-px WebP thumbnail. Scans are incremental (skip "
  "unchanged files by mtime + size), resumable, and prune rows whose files "
  "disappeared. Unreadable or truncated files are still indexed with partial "
  "metadata and a placeholder thumbnail so the user can find and delete them; "
  "magic-byte sniffing corrects mis-extensioned files (e.g. a .MOV saved as .JPG).")

h("5.2  Browsing, Filtering, Sorting", 2)
p("GET /api/photos accepts: free-text (filename / folder / place), date range, "
  "media type, location, camera, person, album, hashtag, year, folder path, "
  "duplicates-only. Sort by date taken, name, size, recently-added or shuffle. "
  "Results are paginated; the frontend grid uses infinite scroll and lazy "
  "thumbnails. Facet counts (years, locations, cameras, totals) drive the "
  "sidebar.")

h("5.3  Folder Tree", 2)
p("GET /api/library/folders returns a nested tree built from every photo\u2019s "
  "relative path, each node carrying a recursive photo count. The sidebar tree is "
  "collapsible per node, has a global show/hide toggle (persisted to "
  "localStorage), auto-expands to the current selection, and filters the gallery "
  "recursively when a folder is clicked.")

h("5.4  Media Viewing", 2)
p("Clicking a tile opens the Lightbox: full image or an HTML5 video player fed by "
  "a range-request endpoint (enables seeking). Keyboard: \u2190 \u2192 navigate, Esc "
  "close. The bottom bar shows metadata and chips for albums, hashtags, people "
  "tags and named faces. For images a 🙂 button toggles face boxes.")

h("5.5  Image Editing", 2)
p("conversion_service performs edits with Pillow and re-indexes the row "
  "(dimensions, hashes, thumbnail). A shared _write() helper handles \u201creplace "
  "in place\u201d vs \u201csave a copy\u201d.")
table(
    ["Operation", "Detail"],
    [
        ["Rotate", "90 / 180 / 270\u00b0, lossless-intent re-encode at quality 92"],
        ["Resize", "By max dimension (aspect kept) or explicit width / height"],
        ["Enhance", "Auto-contrast, plus brightness / contrast / colour / sharpness multipliers"],
        ["Convert", "JPEG / PNG / WebP / TIFF / HEIC, optional EXIF passthrough"],
    ],
)
p("The ImageEditor modal is user-resizable (CSS resize: both). Bulk versions of "
  "rotate, enhance, resize and delete run across the whole selection.")

h("5.6  Albums", 2)
p("Free-form named collections, independent of folders. A photo may be in many "
  "albums. Cover image is auto-set to the first added photo. Added from the "
  "gallery bulk toolbar or the Lightbox; the Albums tab provides a grid view and "
  "remove-from-album.")

h("5.7  Hashtags", 2)
p("Lightweight labels. Names are normalised (lower-cased, stripped of a leading "
  "\u2018#\u2019 and punctuation, spaces \u2192 hyphens, 40-char cap), so \u201c#Sunset Beach!\u201d "
  "becomes sunset-beach. Applied per-photo or in bulk; tags with no photos are "
  "pruned automatically. Chips in the sidebar and Lightbox filter / remove.")

h("5.8  People & Face Recognition", 2)
p("Detection uses InsightFace buffalo_l via ONNX Runtime on CPU; each face is "
  "stored with a 512-dimension normalised embedding. A \u201cDetect faces\u201d run "
  "performs three phases:")
bullet("Detect \u2014 find faces in every image not yet processed (faces_done flag).")
bullet("Recognise \u2014 attach each loose face to the nearest named person\u2019s centroid "
       "(built from confirmed faces, cosine \u2265 0.42) as a suggestion with a "
       "similarity score.")
bullet("Group \u2014 DBSCAN-cluster the remaining faces into \u201cUnnamed N\u201d groups. "
       "Grouping is stable: a new cluster matches an existing unnamed group by "
       "centroid before a new one is created.")
p("Naming an unnamed group confirms all its faces. Creating, renaming or "
  "assigning a person triggers a background re-recognition pass, so accuracy "
  "improves as the user names people. The user reviews suggestions face-by-face "
  "(confirm / reject) in the People panel or directly on the photo via the face "
  "overlay. The model bundle is resolved from a configurable path next to the "
  "database (so a service account can read it) and auto-downloads on first use "
  "with an SSL-verification fallback.")

h("5.9  Duplicate Detection", 2)
p("duplicate_service builds a union-find over two relations: identical content "
  "(equal SHA-256) and near-identical images (perceptual-hash Hamming distance \u2264 "
  "a configurable threshold). Each resulting group suggests the best copy to keep "
  "(most pixels, then largest file) and reports reclaimable bytes. The user "
  "resolves a group manually, marks a pair as \u201cnot a duplicate\u201d, or auto-resolves "
  "all exact / near groups. Removed files go to the Recycle Bin.")

h("5.10  Import & Organisation", 2)
p("import_service copies or moves media from any source folder into "
  "library/YYYY/YYYY-MM-DD/Location/, using the EXIF capture date (falling back "
  "to a date in the filename, then file mtime) and the reverse-geocoded GPS "
  "location (\u201cUnknown location\u201d otherwise). Files already in the library (by "
  "SHA-256) are skipped; name collisions get a numeric suffix. A dry run and a "
  "live plan preview are available; progress and a per-file log stream to the UI.")

h("5.11  Deletion", 2)
p("All deletions \u2014 single, bulk, duplicate resolution, editor \u2014 route through "
  "core/trash.move_to_trash, which sends files to the Windows Recycle Bin "
  "(recoverable) and never unlinks. The database row and cached thumbnail are "
  "removed on success.")

# ================================================================ 6 API
h("6  API Reference", 1)
p("Selected endpoints (48 total). All under /api.")
table(
    ["Method & Path", "Purpose"],
    [
        ["GET /photos", "Filtered, sorted, paginated list"],
        ["GET /photos/{id}", "Detail incl. faces, people tags, hashtags, albums"],
        ["GET /photos/{id}/thumb | /file | /download", "Thumbnail / original (range) / attachment"],
        ["POST /photos/delete", "Bulk delete to Recycle Bin"],
        ["POST /photos/{id}/rotate | resize | enhance | convert", "Image edits"],
        ["GET /photos/facets", "Years, locations, cameras, totals"],
        ["GET /library/status | folders", "Counts + scan progress / folder tree"],
        ["POST /library/scan", "Start incremental or full re-index"],
        ["GET/POST /albums, POST/DELETE /albums/{id}/photos", "Album CRUD + membership"],
        ["GET /tags, POST/DELETE /photos/{id}/tags, POST /tags/bulk", "Hashtags"],
        ["GET /people, POST/PATCH/DELETE /people[/{id}], POST /people/merge", "People"],
        ["POST /faces/detect | recognize | cluster", "Recognition pipeline"],
        ["POST /faces/{id}/assign | confirm | reject", "Per-face review"],
        ["GET /people/{id}/faces?status=", "Confirmed / suggested / all crops"],
        ["GET /duplicates, POST /duplicates/resolve|ignore|auto-resolve", "De-duplication"],
        ["POST /import/plan | run, GET /import/status", "Import"],
        ["GET /library/status, POST /settings", "Runtime settings"],
    ],
)

# ================================================================ 7 Decisions
h("7  Key Design Decisions", 1)
table(
    ["Decision", "Rationale"],
    [
        ["Layered backend, no ORM",
         "SQL is explicit and tunable for a read-heavy 100k-row workload; layers "
         "keep HTTP, rules and SQL separable and testable."],
        ["Single Uvicorn worker",
         "Scan / import / face progress and the loaded face model are in-process "
         "module state; multiple workers would each hold a separate copy."],
        ["SQLite, not a server DB",
         "Single-user, single-machine; zero-ops, file-copy backup, WAL gives "
         "concurrent reads during a scan."],
        ["Parallel scan via threads",
         "Work is I/O- and subprocess-bound (ffprobe, ffmpeg, file hashing); the "
         "GIL is released, so threads give a 3\u20134\u00d7 speed-up without process "
         "overhead."],
        ["Perceptual hash without SciPy",
         "SciPy wheels lag new Python releases; a NumPy-FFT DCT keeps the "
         "dependency surface small."],
        ["Video thumbnail via JPEG frame + Pillow",
         "ffmpeg 9\u2019s native .webp output uses the animated-webp encoder, which "
         "fails on many clips; extracting a JPEG frame and letting Pillow write "
         "the WebP reuses the reliable image path."],
        ["Deletion only to the Recycle Bin",
         "The app manages the user\u2019s irreplaceable originals; every destructive "
         "path must be recoverable."],
        ["Face model beside the database",
         "IIS runs the pool as a service account with no usable home directory; a "
         "configurable INSIGHTFACE_ROOT keeps the model readable."],
        ["Suggestions, not silent auto-tagging",
         "Face recognition is imperfect; every automatic assignment is a "
         "reviewable suggestion until the user confirms it."],
    ],
)

# ================================================================ 8 Deployment
h("8  Deployment & Operations", 1)
p("Deploy-ToIIS.ps1 (run elevated) is idempotent: it builds the virtualenv and "
  "the frontend, writes web.config from a template with this machine\u2019s paths, "
  "creates the app pool (No Managed Code, Always Running, no idle timeout, no "
  "periodic recycle) and site, grants NTFS permissions, and health-checks.")

h("8.1  Pool Identity", 2)
p("The virtualenv\u2019s python.exe depends on the base Python install, which on the "
  "target machine is per-user under %LOCALAPPDATA% and unreadable by low-privilege "
  "service accounts (the user profile denies directory listing to them). "
  "-PoolIdentity selects the trade-off:")
table(
    ["Option", "Notes"],
    [
        ["LocalSystem (default)", "Reads everything, no grants; high privilege, deletes go to the SYSTEM Recycle Bin."],
        ["NetworkService / ApplicationPoolIdentity", "Lower privilege; needs read + traverse grants into the per-user Python / ffmpeg folders."],
        ["-PoolUser MACHINE\\me", "Runs as a real account (prompts for the password); deletes land in that user\u2019s Recycle Bin."],
    ],
)

h("8.2  State & Backup", 2)
bullet("deploy/data/library.db (+ -wal/-shm) \u2014 the catalogue")
bullet("deploy/data/thumbnails/ \u2014 regenerable thumbnail cache")
bullet("deploy/data/insightface/ \u2014 face model bundle (~330 MB)")
bullet("deploy/data/settings.json \u2014 runtime settings")
p("Backing up deploy/data/ preserves people names, tags, ratings, albums and "
  "duplicate decisions. Deleting it forces a rescan; the photos themselves are "
  "never in there.")

h("8.3  Uninstall", 2)
p("Uninstall-FromIIS.ps1 removes the site and pool and strips the NTFS grants it "
  "added (by SID, captured before the pool is deleted). It leaves deploy/data and "
  "the photo library untouched.")

# ================================================================ 9 Security
h("9  Security & Privacy", 1)
for s in [
    "The server binds to 127.0.0.1 only; there is no authentication because there "
    "is no remote surface.",
    "No media, metadata, embeddings or thumbnails are sent anywhere. Reverse "
    "geocoding is offline by default; the Nominatim option is explicit opt-in and "
    "sends only coordinates.",
    "The face model downloads once from GitHub on first use (or is seeded from an "
    "existing copy); an SSL-verification fallback covers corporate MITM proxies.",
    "Media is served with Content-Disposition inline / attachment and HTTP range "
    "support; request filtering allows large streams.",
    "All file removal is to the Recycle Bin.",
]:
    bullet(s)

# ================================================================ 10 Performance
h("10  Performance", 1)
table(
    ["Concern", "Approach"],
    [
        ["First scan of a large library", "Parallel workers; SHA-256 + perceptual hash + thumbnail per file. Video-heavy folders are ffprobe/ffmpeg-bound."],
        ["Gallery scroll", "Server-side pagination, infinite scroll, lazy <img>, 512-px WebP thumbnails."],
        ["Duplicate scan", "O(n\u00b2) perceptual-hash comparison over images; acceptable at current scale, a BK-tree is the next step."],
        ["Face detection", "CPU-only InsightFace, ~1\u20132 images/s; background thread with progress, resumable via faces_done. ~86k images \u2248 several hours."],
        ["Recognition pass", "Vectorised cosine of loose-face embeddings against per-person centroids."],
        ["DB under concurrent scan", "WAL mode; readers never block the single writer."],
    ],
)

# ================================================================ 11 Future
h("11  Limitations & Future Work", 1)
for s in [
    "No map view for geotagged media.",
    "Duplicate detection is image-only and O(n\u00b2); videos are matched by exact hash only.",
    "Face detection has no GPU path; a first full pass on a very large library is slow.",
    "No RAW or HEIC-sequence handling beyond what Pillow provides.",
    "Editing is single-file; no crop / straighten / red-eye tools yet.",
    "Albums have no ordering or nested albums.",
    "No automated test suite in the repository (verification is via scripted end-to-end runs).",
    "Single library root; multiple roots or external volumes are not modelled.",
]:
    bullet(s)

# ================================================================ Appendix
h("Appendix A  Configuration", 1)
p("Environment variables (or ~/.imageviewer/settings.json / deploy/data/settings.json):")
table(
    ["Variable", "Default", "Meaning"],
    [
        ["PHOTO_LIBRARY", "D:\\PhotoLibrary", "Managed library root"],
        ["IMAGEVIEWER_DATA", "~/.imageviewer", "DB, thumbnails, model, settings"],
        ["IMAGEVIEWER_HOST / PORT", "127.0.0.1 / 8077", "Bind address (IIS injects the port)"],
        ["FFMPEG_BINARY / FFPROBE_BINARY", "(PATH)", "Explicit ffmpeg / ffprobe paths"],
        ["INSIGHTFACE_ROOT", "<data>/insightface", "Face model location"],
    ],
)
p("Runtime settings editable in the UI: library path, import mode (copy / move), "
  "near-duplicate threshold, geocoding mode, scan worker count.")

doc.add_paragraph()
end = doc.add_paragraph()
end.alignment = WD_ALIGN_PARAGRAPH.CENTER
er = end.add_run("\u2014 End of document \u2014")
er.italic = True
er.font.size = Pt(9)

doc.save(str(OUT))
print("wrote", OUT, OUT.stat().st_size, "bytes")
