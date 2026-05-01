import asyncio
from fastapi import APIRouter

from app.services.route_client import get_route, get_routes_list
from app.adapters.route_adapter import build_transit_route

router = APIRouter(
    prefix="/api/v1/routes",
    tags=["Routes"]
)

@router.get("/{route_id}/transit-data")
async def get_transit_route(route_id: str):
    geojson = await get_route(route_id)
    return build_transit_route(geojson)

@router.get("/all-transit-data")
async def get_all_transit_routes():
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
