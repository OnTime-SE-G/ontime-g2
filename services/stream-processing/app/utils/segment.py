"""Highway geo-fence helpers for dual-segment ETA (SRS FR-G2-01)."""

from __future__ import annotations

import os

# Kahathuduwa expressway corridor bounding box (approximate, configurable via env)
_DEFAULT_BOUNDS = {
    "min_lat": 6.7800,
    "max_lat": 6.8200,
    "min_lon": 79.9600,
    "max_lon": 80.0200,
}


def _bounds() -> dict[str, float]:
    return {
        "min_lat": float(os.environ.get("SEGMENT_EXPRESSWAY_MIN_LAT", _DEFAULT_BOUNDS["min_lat"])),
        "max_lat": float(os.environ.get("SEGMENT_EXPRESSWAY_MAX_LAT", _DEFAULT_BOUNDS["max_lat"])),
        "min_lon": float(os.environ.get("SEGMENT_EXPRESSWAY_MIN_LON", _DEFAULT_BOUNDS["min_lon"])),
        "max_lon": float(os.environ.get("SEGMENT_EXPRESSWAY_MAX_LON", _DEFAULT_BOUNDS["max_lon"])),
    }


def resolve_segment_mode(lat: float, lon: float) -> str:
    """Return urban or expressway based on geo-fence membership."""
    box = _bounds()
    if (
        box["min_lat"] <= lat <= box["max_lat"]
        and box["min_lon"] <= lon <= box["max_lon"]
    ):
        return "expressway"
    return "urban"
