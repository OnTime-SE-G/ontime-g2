# services/api-gateway/routers/routes.py
# REST endpoints for route and stop data (Issue #20 — ORM SELECT layer).

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.route_service import get_route, get_stops_for_route, list_routes

router = APIRouter(prefix="/api/v1/routes", tags=["routes"])


def _route_to_dict(route) -> Dict[str, Any]:
    return {
        "id": route.id,
        "name": route.name,
    }


def _stop_to_dict(stop) -> Dict[str, Any]:
    return {
        "id": stop.id,
        "route_id": stop.route_id,
        "name": stop.name,
        "stop_order": stop.stop_order,
    }


@router.get("", response_model=List[Dict[str, Any]])
def get_routes(db: Session = Depends(get_db)):
    """List all routes."""
    return [_route_to_dict(r) for r in list_routes(db)]


@router.get("/{route_id}", response_model=Dict[str, Any])
def get_route_by_id(route_id: int, db: Session = Depends(get_db)):
    """Get a single route with its stops."""
    route = get_route(db, route_id)
    if route is None:
        raise HTTPException(status_code=404, detail=f"Route {route_id} not found")
    return {
        **_route_to_dict(route),
        "stops": [_stop_to_dict(s) for s in get_stops_for_route(db, route_id)],
    }
