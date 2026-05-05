from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from database import get_db
from models.orm import RouteORM, StopORM
from models.schemas import RouteResponse, StopResponse

router = APIRouter(prefix="/routes", tags=["routes"])


def _stop_to_schema(stop: StopORM) -> StopResponse:
    lat = lon = None
    if stop.location is not None:
        from shapely import wkb
        pt = wkb.loads(bytes(stop.location.data))
        lat, lon = pt.y, pt.x
    return StopResponse(id=stop.id, name=stop.name, stop_order=stop.stop_order, lat=lat, lon=lon)


@router.get("/", response_model=List[RouteResponse])
def list_routes(db: Session = Depends(get_db)):
    routes = db.query(RouteORM).options(joinedload(RouteORM.stops)).all()
    return [
        RouteResponse(
            id=r.id,
            name=r.name,
            stops=[_stop_to_schema(s) for s in sorted(r.stops, key=lambda s: s.stop_order)],
        )
        for r in routes
    ]


@router.get("/{route_id}", response_model=RouteResponse)
def get_route(route_id: int, db: Session = Depends(get_db)):
    route = (
        db.query(RouteORM)
        .options(joinedload(RouteORM.stops))
        .filter(RouteORM.id == route_id)
        .first()
    )
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteResponse(
        id=route.id,
        name=route.name,
        stops=[_stop_to_schema(s) for s in sorted(route.stops, key=lambda s: s.stop_order)],
    )
