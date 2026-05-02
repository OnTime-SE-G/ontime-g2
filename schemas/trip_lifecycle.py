from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TripLifecycleEventType = Literal["TRIP_STARTED", "TRIP_ENDED"]


class TripLifecycleEvent(BaseModel):
    """Trip lifecycle event produced by Fleet and consumed by ingestion/Flink."""

    model_config = ConfigDict(populate_by_name=True)

    event: TripLifecycleEventType
    bus_id: str = Field(..., min_length=1, max_length=50, alias="busId")
    trip_id: str = Field(..., min_length=1, max_length=50, alias="tripId")
    route_id: str = Field(..., min_length=1, max_length=50, alias="routeId")
    timestamp: datetime
