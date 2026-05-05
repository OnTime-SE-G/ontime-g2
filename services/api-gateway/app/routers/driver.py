# services/api-gateway/app/routers/driver.py
# Driver-facing trip lifecycle endpoints.
# NOTE for G4/Kong: All routes under /api/v1/driver require driver-role authentication.

from fastapi import APIRouter, HTTPException
from httpx import HTTPStatusError

from app.services.fleet_client import (
    get_today_trips,
    start_planned_trip,
    end_planned_trip,
    report_trip_delay,
    report_trip_incident,
)
from app.schemas import PlannedTripResponse, TripLifecycleResponse, TripDelayReport, TripIncidentReport

router = APIRouter(
    prefix="/api/v1/driver",
    tags=["Driver"],
    # NOTE for G4/Kong: All routes under this prefix require driver-level authentication.
)


@router.get("/trips/today", response_model=list[PlannedTripResponse])
async def get_my_trips():
    """
    Get today's timetable.

    Driver view of the planned trip list for today. The driver app uses this
    to display which trips have been assigned to them and which can be started.
    """
    try:
        return await get_today_trips()
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/trips/{trip_id}/start", response_model=PlannedTripResponse)
async def start_trip(trip_id: str):
    """
    Start a planned trip.

    Driver only. Transitions the trip from WAITING_AT_DEPOT to EN_ROUTE.
    This triggers a Kafka event that activates GPS tracking for
    the assigned bus — the Ingestion Service will begin accepting
    GPS messages from the bus immediately after.

    The trip must have a bus and driver assigned before it can be started.
    """
    try:
        return await start_planned_trip(trip_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/trips/{trip_id}/end", response_model=PlannedTripResponse)
async def end_trip(trip_id: str):
    """
    End an active trip.

    Driver only. Transitions the trip from EN_ROUTE to ARRIVED_DESTINATION.
    This triggers a Kafka event that deactivates GPS tracking for
    the assigned bus.
    """
    try:
        return await end_planned_trip(trip_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/trips/{trip_id}/report-delay", response_model=PlannedTripResponse)
async def report_delay(trip_id: str, report: TripDelayReport):
    """
    Report a delay in minutes.

    Driver only. Persists the delay for the ETA engine to apply offsets.
    positive = delay, negative = ahead of schedule.
    """
    try:
        return await report_trip_delay(trip_id, report.delay_minutes)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/trips/{trip_id}/report-incident", response_model=PlannedTripResponse)
async def report_incident(trip_id: str, report: TripIncidentReport):
    """
    Report an incident (BREAKDOWN, ACCIDENT, etc.).

    Driver only. Transitions the trip to INCIDENT_REPORTED state and triggers an admin alert.
    """
    try:
        return await report_trip_incident(trip_id, report.incident_type, report.message)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
