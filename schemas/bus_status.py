# schemas/bus_status.py
# Canonical bus lifecycle state contract for the OnTime platform.
# Used by: API gateway, stream processing, ingestion service.

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class BusLifecycleState(str, Enum):
    """
    Bus state machine states (SRS v2.0 FR-G3.2).

    WAITING_AT_DEPOT -> DEPARTED_ORIGIN -> EN_ROUTE -> ARRIVED_DESTINATION
                                              |
                                       INCIDENT_REPORTED
    ARRIVED_DESTINATION -> WAITING_AT_DEPOT  (Admin reset)
    """

    WAITING_AT_DEPOT = "WAITING_AT_DEPOT"
    DEPARTED_ORIGIN = "DEPARTED_ORIGIN"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED_DESTINATION = "ARRIVED_DESTINATION"
    INCIDENT_REPORTED = "INCIDENT_REPORTED"


class BusStatusMessage(BaseModel):
    """
    Message representing a bus state transition event.

    Python fields use snake_case. For JSON serialization (Kafka, API responses),
    use model.model_dump(by_alias=True) to get camelCase output.
    """

    model_config = ConfigDict(populate_by_name=True)

    bus_id: str = Field(..., min_length=1, max_length=50, alias="busId")
    trip_id: str = Field(..., min_length=1, max_length=50, alias="tripId")
    route_id: str = Field(..., min_length=1, max_length=50, alias="routeId")
    state: BusLifecycleState
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
