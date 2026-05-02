from typing import List
from fastapi import APIRouter

from app.services.route_client import (
    get_all_stops, get_nearby_stops, get_routes_for_stop
)
from app.schemas import (
    StopAggregatedResponse, StopNearbyResponse, RouteSummary
)

router = APIRouter(
    prefix="/api/v1/stops",
    tags=["Stops"]
)

@router.get("", response_model=List[StopAggregatedResponse])
@router.get("/", response_model=List[StopAggregatedResponse])
async def list_all_stops():
    """
    List all deduplicated bus stops across the entire network.

    Used by the frontend to display the master list of all stops on the map.
    Returns the physical stops and aggregates the routes that pass through them.
    """
    return await get_all_stops()

@router.get("/nearby", response_model=List[StopNearbyResponse])
async def nearby_stops(lat: float, lon: float, radius_m: int = 500):
    """
    Find bus stops near a specific coordinate.

    Uses spatial proximity to find all stops within the given radius of the
    provided latitude and longitude. Returns the stops sorted from nearest to farthest.
    """
    return await get_nearby_stops(lat, lon, radius_m)

@router.get("/{stop_id}/routes", response_model=List[RouteSummary])
async def routes_for_stop(stop_id: str):
    """
    Get all routes that pass through a specific bus stop.

    Returns a list of route summaries for all routes that service this physical stop.
    """
    return await get_routes_for_stop(stop_id)
