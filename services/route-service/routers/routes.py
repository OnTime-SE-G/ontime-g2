from fastapi import APIRouter, HTTPException

from services.route_service import (
    fetch_routes,
    fetch_route,
    fetch_route_stops,
)

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("")
def list_routes():
    return fetch_routes()


@router.get("/{route_id}")
def get_route(route_id: int):
    route = fetch_route(route_id)

    if route is None:
        raise HTTPException(
            status_code=404,
            detail="Route not found"
        )

    return route


@router.get("/{route_id}/stops")
def get_stops(route_id: int):
    return fetch_route_stops(route_id)