from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from app.database import get_db
from app.models.db_route import RouteORM, StopORM, RouteStopLinkORM

router = APIRouter(
    prefix="/internal/routes",
    tags=["Internal"]
)

@router.get("/geometry")
def get_all_route_geometries(db: Session = Depends(get_db)):
    """
    Export all route geometries for stream processing and anomaly detection caches.
    Returns a list of routes with their IDs and GeoJSON geometries.
    """
    routes = db.query(RouteORM).all()

    results = []
    for route in routes:
        # Get geometry as GeoJSON
        geojson_raw = db.scalar(
            db.query(func.ST_AsGeoJSON(RouteORM.geometry))
            .filter(RouteORM.id == route.id)
            .statement
        )

        results.append({
            "id": route.id,
            "name": route.name,
            "geometry": json.loads(geojson_raw) if geojson_raw else None
        })

    return results


@router.get("/{routeId}/stops")
def get_route_stops(routeId: int, db: Session = Depends(get_db)):
    """
    Return all stops for a route ordered by stop_order.
    Used by Flink at startup to cache stop sequences for stopsAhead computation.
    Response: [{id, name, stop_order, lat, lon}, ...]
    """
    rows = (
        db.query(
            RouteStopLinkORM.stop_order,
            StopORM.id,
            StopORM.name,
            func.ST_Y(StopORM.location).label("lat"),
            func.ST_X(StopORM.location).label("lon"),
        )
        .join(StopORM, RouteStopLinkORM.stop_id == StopORM.id)
        .filter(RouteStopLinkORM.route_id == routeId)
        .order_by(RouteStopLinkORM.stop_order)
        .all()
    )

    return [
        {
            "id": row.id,
            "name": row.name,
            "stop_order": row.stop_order,
            "lat": float(row.lat) if row.lat is not None else None,
            "lon": float(row.lon) if row.lon is not None else None,
        }
        for row in rows
    ]
