"""Data-access layer. All SQL for the app lives in this package.

Services call these functions; nothing here knows about HTTP or FastAPI.
"""
from . import duplicates, geocode, people, photos

__all__ = ["photos", "people", "duplicates", "geocode"]
