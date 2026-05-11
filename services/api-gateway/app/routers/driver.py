# services/api-gateway/app/routers/driver.py
# Driver-facing trip lifecycle endpoints.
# NOTE for G4/Kong: All routes under /api/v1/driver require driver-role authentication.

import base64
import json
import logging

from fastapi import APIRouter, HTTPException, Header
from httpx import HTTPStatusError
from typing import Optional

from app.services.fleet_client import (
    get_today_trips,
    get_trip_detail,
    get_driver_by_auth_id,
    start_planned_trip,
    end_planned_trip,
    report_trip_delay,
    report_trip_incident,
)
from app.schemas import PlannedTripResponse, TripLifecycleResponse, TripDelayReport, TripIncidentReport, DriverProfile

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/driver",
    tags=["Driver"],
    # NOTE for G4/Kong: All routes under this prefix require driver-level authentication.
)


def _extract_sub_from_jwt(authorization: Optional[str]) -> Optional[str]:
    """
    Decode the JWT payload (without verifying signature) and return the 'sub' claim.
    Kong has already validated the token upstream — this is safe.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    try:
        # JWT payload is the second segment, base64url-encoded
        payload_b64 = token.split(".")[1]
        padding = 4 - len(payload_b64) % 4
        payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub")
    except Exception:
        logger.warning("Failed to decode JWT payload for /driver/me", exc_info=True)
        return None


@router.get("/me", response_model=DriverProfile)
async def get_my_profile(authorization: Optional[str] = Header(default=None)):
    """
    Return the fleet profile for the currently authenticated driver.

    Decodes the Keycloak JWT to extract auth_user_id (sub), then looks up
    the matching driver in Fleet Management.
    """
    auth_user_id = _extract_sub_from_jwt(authorization)
    if not auth_user_id:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization token")
    try:
        return await get_driver_by_auth_id(auth_user_id)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Driver profile not found for this user")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/trips/today", response_model=list[PlannedTripResponse])
async def get_my_trips(driver_id: Optional[int] = None):
    """
    Get today's timetable.

    Pass ?driver_id={id} to filter trips assigned to a specific driver.
    The driver's fleet id can be obtained from GET /api/v1/driver/me.
    """
    try:
        return await get_today_trips(driver_id=driver_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/trips/{trip_id}", response_model=PlannedTripResponse)
async def get_trip(trip_id: str):
    """
    Get full details of a single planned trip.

    Driver view — useful for loading trip state before starting or after resuming.
    """
    try:
        return await get_trip_detail(trip_id)
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
