# schemas/gps.py
# Canonical GPS data contract for the OnTime platform.
# Used by: GPS simulator, ingestion service, stream processing, API gateway.

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GPSLocationMessage(BaseModel):
    """
    GPS telemetry message sent by G1 devices over MQTT.

    G1 sends bus identity and event-time location only. It does not send
    tripId; ingestion adds the active tripId after checking trip.lifecycle.
    """

    model_config = ConfigDict(populate_by_name=True)

    bus_id: str = Field(..., min_length=1, max_length=50, alias="busId")

    lat: float
    lon: float

    speed: float = Field(..., ge=0, le=200)
    heading: float = Field(default=0, ge=0, le=360)

    timestamp: datetime

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


class GPSMessage(GPSLocationMessage):
    """
    Enriched GPS telemetry message published by ingestion to Kafka.

    Python fields use snake_case. For JSON serialization (Kafka, API responses),
    use model.model_dump(by_alias=True) to get camelCase output.
    """

    trip_id: str = Field(..., min_length=1, max_length=50, alias="tripId")
