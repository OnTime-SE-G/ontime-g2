from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class BusLifecycleState(str, Enum):
    WAITING_AT_DEPOT = "WAITING_AT_DEPOT"
    DEPARTED_ORIGIN = "DEPARTED_ORIGIN"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED_DESTINATION = "ARRIVED_DESTINATION"
    INCIDENT_REPORTED = "INCIDENT_REPORTED"


class BusStatusMessage(BaseModel):
    bus_id: str = Field(..., min_length=1, max_length=50)
    trip_id: str = Field(..., min_length=1, max_length=50)
    state: BusLifecycleState
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))


class BusState(str, Enum):
    WAITING_AT_DEPOT = "WAITING_AT_DEPOT"
    DEPARTED_ORIGIN = "DEPARTED_ORIGIN"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED_DESTINATION = "ARRIVED_DESTINATION"
    INCIDENT_REPORTED = "INCIDENT_REPORTED"


class BusStatusEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    busId: str = Field(min_length=1)
    tripId: str = Field(min_length=1)
    routeId: str = Field(min_length=1)
    state: BusState
    timestamp: datetime
