"""Pydantic DTOs for the API layer. Kept separate from persistence rows."""
from pydantic import BaseModel, Field


# ---------- photos ----------

class PhotoFilters(BaseModel):
    q: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    media_type: str | None = None
    location: str | None = None
    camera: str | None = None
    person_id: int | None = None
    year: int | None = None
    duplicates_only: bool = False
    sort: str = "date"
    order: str = "desc"
    limit: int = Field(120, ge=1, le=500)
    offset: int = Field(0, ge=0)


class FaceBox(BaseModel):
    id: int
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_w: int | None = None
    bbox_h: int | None = None
    person_id: int | None = None
    name: str | None = None


class PersonTag(BaseModel):
    id: int
    name: str


class PhotoOut(BaseModel):
    id: int
    path: str
    rel_path: str
    filename: str
    ext: str
    media_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    taken_at: str | None = None
    date_source: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    location: str | None = None
    orientation: int | None = 1
    sha256: str | None = None
    phash: str | None = None
    rating: int = 0


class PhotoDetail(PhotoOut):
    faces: list[FaceBox] = []
    people_tags: list[PersonTag] = []


class PhotoPage(BaseModel):
    total: int
    items: list[PhotoOut]
    limit: int
    offset: int


class LocationFacet(BaseModel):
    location: str
    n: int


class Counts(BaseModel):
    total: int = 0
    images: int = 0
    videos: int = 0
    bytes: int = 0


class Facets(BaseModel):
    years: list[str] = []
    locations: list[LocationFacet] = []
    cameras: list[str] = []
    counts: Counts = Counts()


class DeleteRequest(BaseModel):
    ids: list[int]


class DeleteResult(BaseModel):
    removed: list[int] = []
    errors: list[dict] = []


class RatingRequest(BaseModel):
    rating: int = Field(ge=0, le=5)


# ---------- library ----------

class Settings(BaseModel):
    library_path: str
    import_mode: str
    near_duplicate_threshold: int
    geocode: str
    nominatim_email: str = ""
    scan_workers: int = 4


class SettingsPatch(BaseModel):
    library_path: str | None = None
    import_mode: str | None = None
    near_duplicate_threshold: int | None = None
    geocode: str | None = None
    nominatim_email: str | None = None
    scan_workers: int | None = None


class ScanRequest(BaseModel):
    full: bool = False


class JobStarted(BaseModel):
    started: bool
    reason: str | None = None


class LibraryStatus(BaseModel):
    settings: Settings
    library_exists: bool
    counts: dict
    scan: dict


# ---------- people / faces ----------

class PersonOut(BaseModel):
    id: int
    name: str
    auto: int = 0
    cover_face: int | None = None
    face_count: int = 0
    photo_count: int = 0


class PersonCreate(BaseModel):
    name: str


class MergeRequest(BaseModel):
    source_id: int
    target_id: int


class FaceAssign(BaseModel):
    person_id: int | None = None
    name: str | None = None


class TagRequest(BaseModel):
    person_id: int


class DetectRequest(BaseModel):
    limit: int | None = None


class FaceEngineStatus(BaseModel):
    engine_available: bool
    load_error: str | None = None
    faces: int
    named_faces: int
    photos_pending: int
    progress: dict


# ---------- duplicates ----------

class DuplicatePhoto(BaseModel):
    id: int
    filename: str
    rel_path: str
    path: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    taken_at: str | None = None
    media_type: str


class DuplicateGroup(BaseModel):
    kind: str
    suggested_keep: int
    photos: list[DuplicatePhoto]
    wasted_bytes: int


class DuplicateReport(BaseModel):
    groups: list[DuplicateGroup]
    group_count: int
    reclaimable_bytes: int


class ResolveRequest(BaseModel):
    keep_id: int
    remove_ids: list[int]


class IgnoreRequest(BaseModel):
    a: int
    b: int


class AutoResolveRequest(BaseModel):
    kinds: list[str] = ["exact"]


# ---------- import ----------

class SourceRequest(BaseModel):
    source: str


class ImportRunRequest(BaseModel):
    source: str
    dry_run: bool = False


class ImportPlanItem(BaseModel):
    source: str
    target: str
    size_bytes: int


class ImportPlan(BaseModel):
    total_media: int
    already_in_library: int
    to_import: int
    preview: list[ImportPlanItem]
    mode: str


# ---------- convert ----------

class ConvertRequest(BaseModel):
    target: str
    max_dimension: int | None = None
    quality: int = Field(90, ge=1, le=100)
    keep_exif: bool = True
    overwrite: bool = False


class ConvertResult(BaseModel):
    output: str
    size_bytes: int
    photo_id: int | None = None
    replaced: bool
