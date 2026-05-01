from fastapi import APIRouter

from app.services.fleet_client import get_buses
from app.adapters.bus_adapter import build_bus_data

router = APIRouter(
    prefix="/api/v1/buses",
    tags=["Buses"]
)

@router.get("/live")
async def get_live_buses():
    buses = await get_buses()

    # later: fetch real-time tracking here
    live_map = {}

    return [
        build_bus_data(bus, live_map.get(bus["id"]))
        for bus in buses
    ]
