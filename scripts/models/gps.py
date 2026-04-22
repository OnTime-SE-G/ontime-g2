# scripts/models/gps.py

from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class GPSMessage(BaseModel):
    bus_id: str = Field(..., min_length=1, max_length=50)
    trip_id: str = Field(..., min_length=1, max_length=50)

    lat: float
    lon: float

    speed: float = Field(..., ge=0, le=200)
    heading: float = Field(default=0, ge=0, le=360)

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

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