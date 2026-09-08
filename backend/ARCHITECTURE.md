# Backend architecture

Four layers, each depending only on the one below it.

```
routers/         HTTP only — parse request, call a service, shape the response.
                 No SQL, no business rules, no file I/O.
   │
services/        Business logic & orchestration. Raises domain errors
                 (app.core.errors). Never imports FastAPI.
   │
repositories/    Every SQL statement in the app. Returns sqlite3.Row / plain
                 values. No business rules.
   │
database.py      Connection + schema.
```

Plus:

- **`schemas.py`** — Pydantic request/response DTOs, used by routers (and a few
  service return types). Distinct from persistence rows.
- **`core/`** — cross-cutting helpers: `errors.py` (domain exception types +
  the FastAPI handler that maps them to status codes), `trash.py` (the only code
  that deletes files — always to the Recycle Bin).
- **Processing modules** in `services/` (`exif`, `hashing`, `thumbnails`,
  `imaging`, `geocoding`, `indexer`, `face_engine`) — pure media/ML work. They
  may use `repositories/` but hold no HTTP concerns.

## Services

| Module | Responsibility |
|--------|----------------|
| `library_service` | Scan loop + progress, library status, settings. |
| `photo_service` | Search/filter, detail, delete (→ trash + thumb cleanup), rating, facets. |
| `people_service` | People CRUD, merge, face assignment, photo tags, face-engine control. |
| `duplicate_service` | Union-find grouping (exact SHA-256 + perceptual hash), resolve / auto-resolve / ignore. |
| `import_service` | Plan + run import into `YYYY/YYYY-MM-DD/Location`. |
| `conversion_service` | Format conversion / resize, in place or as a copy. |

## Error flow

A service raises `NotFound` / `BadRequest` / `Conflict` / `DependencyMissing`
(`app.core.errors`). `install_error_handlers(app)` in `main.py` turns any
`AppError` into `{"detail": ..., "code": ...}` with the matching status code.
Routers contain no `try/except` for domain failures.

## Adding an endpoint

1. Add request/response models to `schemas.py`.
2. Add the SQL to the relevant `repositories/*.py`.
3. Add the orchestration to a `services/*_service.py` (raise domain errors).
4. Add a thin route in `routers/*.py` with `response_model=`.
