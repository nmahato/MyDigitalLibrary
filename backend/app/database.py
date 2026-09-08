import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id              INTEGER PRIMARY KEY,
    path            TEXT UNIQUE NOT NULL,
    rel_path        TEXT NOT NULL,
    filename        TEXT NOT NULL,
    ext             TEXT NOT NULL,
    media_type      TEXT NOT NULL,           -- image | video
    size_bytes      INTEGER NOT NULL,
    width           INTEGER,
    height          INTEGER,
    duration_sec    REAL,
    taken_at        TEXT,                    -- ISO8601, best guess
    date_source     TEXT,                    -- exif | filename | mtime
    fs_modified     TEXT,
    camera_make     TEXT,
    camera_model    TEXT,
    gps_lat         REAL,
    gps_lon         REAL,
    location        TEXT,
    orientation     INTEGER DEFAULT 1,
    sha256          TEXT,
    phash           TEXT,
    rating          INTEGER DEFAULT 0,
    indexed_at      TEXT,
    faces_done      INTEGER DEFAULT 0,
    missing         INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_photos_taken   ON photos(taken_at);
CREATE INDEX IF NOT EXISTS idx_photos_sha     ON photos(sha256);
CREATE INDEX IF NOT EXISTS idx_photos_phash   ON photos(phash);
CREATE INDEX IF NOT EXISTS idx_photos_loc     ON photos(location);
CREATE INDEX IF NOT EXISTS idx_photos_type    ON photos(media_type);

CREATE TABLE IF NOT EXISTS people (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    cover_face  INTEGER,
    auto        INTEGER DEFAULT 0,          -- 1 = auto-created from a cluster
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS faces (
    id          INTEGER PRIMARY KEY,
    photo_id    INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    person_id   INTEGER REFERENCES people(id) ON DELETE SET NULL,
    bbox_x      INTEGER, bbox_y INTEGER, bbox_w INTEGER, bbox_h INTEGER,
    det_score   REAL,
    embedding   BLOB,
    cluster_id  INTEGER,
    confirmed   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_faces_photo   ON faces(photo_id);
CREATE INDEX IF NOT EXISTS idx_faces_person  ON faces(person_id);
CREATE INDEX IF NOT EXISTS idx_faces_cluster ON faces(cluster_id);

-- photo-level people tags (works with no face model)
CREATE TABLE IF NOT EXISTS photo_people (
    photo_id   INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (photo_id, person_id)
);

CREATE TABLE IF NOT EXISTS dup_ignored (
    a INTEGER NOT NULL,
    b INTEGER NOT NULL,
    PRIMARY KEY (a, b)
);

CREATE TABLE IF NOT EXISTS geocode_cache (
    key   TEXT PRIMARY KEY,   -- rounded "lat,lon"
    label TEXT
);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
