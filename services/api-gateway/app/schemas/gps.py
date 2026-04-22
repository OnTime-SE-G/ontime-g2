from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class GPSPayload(BaseModel):
    bus_id: str = Field(..., min_length=1, max_length=50)
    route_id: str = Field(..., min_length=1, max_length=50)
    lat: float
    lng: float
    speed: float = Field(..., ge=0, le=200)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, value: float) -> float:
        if value < -90 or value > 90:
            raise ValueError("Latitude must be between -90 and 90")
        return value

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, value: float) -> float:
        if value < -180 or value > 180:
            raise ValueError("Longitude must be between -180 and 180")
        return value


class GPSReading(BaseModel):
    model_config = ConfigDict(extra="forbid")

    busId: str = Field(min_length=1)
    routeId: str = Field(min_length=1)
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    speed: float = Field(ge=0.0)
    satellites: int = Field(ge=0)
    deviation: float = Field(ge=0.0)
    timestamp: datetime
