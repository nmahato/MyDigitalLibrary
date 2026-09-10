"""Data-access layer. All SQL for the app lives in this package.

Services call these functions; nothing here knows about HTTP or FastAPI.
"""
from . import albums, duplicates, geocode, people, photos, tags

__all__ = ["photos", "people", "duplicates", "geocode", "albums", "tags"]
