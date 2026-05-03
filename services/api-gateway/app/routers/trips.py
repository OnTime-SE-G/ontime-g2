from fastapi import APIRouter, HTTPException
from httpx import HTTPStatusError
from app.services.fleet_client import get_trip_detail
from app.schemas import PlannedTripResponse

router = APIRouter(
    prefix="/api/v1/trips",
    tags=["Trips"]
)

@router.get("/{trip_id}/state", response_model=PlannedTripResponse)
async def fetch_trip_state(trip_id: str):
    """
    Get the current state of a specific trip.
    
    Includes status, delays, and performance timestamps.
    """
    try:
        return await get_trip_detail(trip_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
