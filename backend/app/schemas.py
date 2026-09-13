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
    face_id: int | None = None
    similar_face_id: int | None = None
    min_similarity: float | None = None
    album_id: int | None = None
    tag: str | None = None
    year: int | None = None
    folder: str | None = None
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
    auto: int | None = None
    confirmed: int = 0
    similarity: float | None = None


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


class NamedRef(BaseModel):
    id: int
    name: str


class PhotoDetail(PhotoOut):
    faces: list[FaceBox] = []
    people_tags: list[PersonTag] = []
    hashtags: list[NamedRef] = []
    albums: list[NamedRef] = []


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


class FolderNode(BaseModel):
    name: str
    path: str
    count: int
    children: list["FolderNode"] = []


FolderNode.model_rebuild()


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
    confirmed_count: int = 0
    suggested_count: int = 0
    photo_count: int = 0


class PersonCreate(BaseModel):
    name: str


class MergeRequest(BaseModel):
    source_id: int
    target_id: int


class SimilarFace(BaseModel):
    id: int
    photo_id: int
    similarity: float
    confirmed: int = 0
    person_id: int | None = None
    person_name: str | None = None
    photo_filename: str | None = None
    photo_rel_path: str | None = None
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_w: int | None = None
    bbox_h: int | None = None


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
    faces: int = 0
    named_faces: int = 0
    unassigned_faces: int = 0
    suggested_faces: int = 0
    unnamed_groups: int = 0
    photos_pending: int = 0
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

class AlbumOut(BaseModel):
    id: int
    name: str
    photo_count: int = 0
    cover_photo: int | None = None
    created_at: str | None = None


class AlbumCreate(BaseModel):
    name: str


class AlbumPhotos(BaseModel):
    photo_ids: list[int]


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
    width: int | None = None
    height: int | None = None
    photo_id: int | None = None
    replaced: bool


class RotateRequest(BaseModel):
    degrees: int = 90            # clockwise; 90 | 180 | 270
    overwrite: bool = True


class ResizeRequest(BaseModel):
    max_dimension: int | None = Field(None, ge=16, le=20000)
    width: int | None = Field(None, ge=1, le=20000)
    height: int | None = Field(None, ge=1, le=20000)
    overwrite: bool = True


class EnhanceRequest(BaseModel):
    auto: bool = True
    brightness: float = Field(1.0, ge=0.1, le=3.0)
    contrast: float = Field(1.0, ge=0.1, le=3.0)
    color: float = Field(1.0, ge=0.0, le=3.0)
    sharpness: float = Field(1.0, ge=0.0, le=4.0)
    overwrite: bool = True
