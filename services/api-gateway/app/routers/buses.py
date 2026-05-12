from typing import List
from fastapi import APIRouter, HTTPException
from httpx import HTTPStatusError

from app.services.fleet_client import (
    get_buses, get_bus, get_route_buses
)
from app.adapters.bus_adapter import build_bus_data
from app.schemas import BusResponse, LiveBusResponse

router = APIRouter(
    prefix="/api/v1/buses",
    tags=["Buses"]
)

@router.get("/live", response_model=List[LiveBusResponse])
async def get_live_buses():
    """
    Get live tracking data for all buses.

    Currently acts as a placeholder structure combining basic bus data with 
    stubbed real-time tracking coordinates.
    """
    buses = await get_buses()

    # later: fetch real-time tracking here
    live_map = {}

    return [
        build_bus_data(bus, live_map.get(bus["id"]))
        for bus in buses
    ]

@router.get("/route/{route_id}", response_model=List[BusResponse])
async def fetch_buses_by_route(route_id: str):
    """
    Get all buses assigned to a specific route.

    Useful for tracking the number of active vehicles on a given route.
    """
    try:
        buses = await get_route_buses(route_id)
        return [
            {
                **b,
                "id": str(b["id"]),
                "route_id": str(b["route_id"]) if b.get("route_id") is not None else None,
            }
            for b in buses
        ]
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router.get("/{bus_id}", response_model=BusResponse)
async def fetch_bus(bus_id: str):
    """
    Get information about a specific bus.

    Returns the basic details, status, and assigned route of the bus.
    """
    try:
        return await get_bus(bus_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
