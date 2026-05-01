import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter

from app.services.route_client import (
    get_route, get_routes_list, search_routes,
    get_route_progress, get_route_stops, get_route_buses
)
from app.adapters.route_adapter import build_transit_route
from app.schemas import (
    RouteSummary, RouteSearchResponse, RouteProgressResponse,
    RouteStopsResponse, RouteBusesResponse
)

router = APIRouter(
    prefix="/api/v1/routes",
    tags=["Routes"]
)

@router.get("", response_model=List[RouteSummary])
@router.get("/", response_model=List[RouteSummary])
async def get_routes():
    """
    List all available routes.

    Returns a simple list of routes including their IDs, names, and numbers.
    Does not include detailed geometry.
    """
    return await get_routes_list()

@router.get("/search", response_model=RouteSearchResponse)
async def search_for_routes(start_lat: float, start_lon: float, end_lat: float, end_lon: float, radius_m: int = 500):
    """
    Search for routes connecting a start coordinate to an end coordinate.

    Finds all bus stops within the given radius of both start and end coordinates,
    then returns the valid routes connecting them in the correct direction of travel.
    """
    return await search_routes(start_lat, start_lon, end_lat, end_lon, radius_m)

@router.get("/{route_id}/transit-data", response_model=Dict[str, Any])
async def get_transit_route(route_id: str):
    """
    Get formatted transit data for a single route.

    Fetches the GeoJSON data for the route and processes it to fit
    the frontend transit data adapter format.
    """
    geojson = await get_route(route_id)
    return build_transit_route(geojson)

@router.get("/all-transit-data", response_model=Dict[str, Any])
async def get_all_transit_routes():
    """
    Get formatted transit data for all routes.

    Fetches all routes and their GeoJSON geometries in parallel,
    returning a mapped dictionary of transit data for frontend consumption.
    """
    routes = await get_routes_list()  # list of {id, name}

    tasks = [
        get_route(str(route["id"]))
        for route in routes
    ]

    geojson_list = await asyncio.gather(*tasks)

    result = {}

    for geojson in geojson_list:
        transit_route = build_transit_route(geojson)
        result[transit_route["id"]] = transit_route

    return result

@router.get("/{route_id}/progress", response_model=RouteProgressResponse)
async def route_progress(route_id: str, lat: float, lon: float, target_stop_order: int):
    """
    Calculate a bus's progress along a route.

    Returns the travelled distance, remaining distance, and progress percentage
    toward a specific target stop order on the given route.
    """
    return await get_route_progress(route_id, lat, lon, target_stop_order)

@router.get("/{route_id}/stops", response_model=RouteStopsResponse)
async def route_stops(route_id: str):
    """
    List all stops for a specific route.

    Returns the stops in order of travel along with the route details.
    """
    return await get_route_stops(route_id)

@router.get("/{route_id}/buses", response_model=RouteBusesResponse)
async def route_buses(route_id: str):
    """
    List live buses assigned to a route.

    Currently acts as a placeholder or forwards to the route-service bus endpoint.
    """
    return await get_route_buses(route_id)
