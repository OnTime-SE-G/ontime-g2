# scripts/models/route.py

from typing import List, Tuple
from pydantic import BaseModel, Field, field_validator


class Stop(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    lat: float
    lon: float
    stop_order: int | None = None

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return value

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return value


class RouteGeometry(BaseModel):
    coordinates: List[Tuple[float, float]]

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: List[Tuple[float, float]]):
        if len(value) < 2:
            raise ValueError("A route needs at least 2 coordinate points")

        for lon, lat in value:
            if not -180 <= lon <= 180:
                raise ValueError(f"Invalid longitude: {lon}")
            if not -90 <= lat <= 90:
                raise ValueError(f"Invalid latitude: {lat}")

        return value


class RouteSeed(BaseModel):
    name: str = Field(..., min_length=3, max_length=150)
    geometry: RouteGeometry
    stops: List[Stop]

    @field_validator("stops")
    @classmethod
    def validate_stop_count(cls, value: List[Stop]):
        if len(value) < 20:
            raise ValueError("At least 20 stops are required")

        # Auto-assign stop order if missing
        for index, stop in enumerate(value, start=1):
            if stop.stop_order is None:
                stop.stop_order = index

        return value