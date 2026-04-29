#services/route-service/app/routers/routes.py

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2 import Geography
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from app.database import get_db
from app.models.db_route import RouteORM, StopORM

router = APIRouter(
    prefix="/api/v1/routes",
    tags=["Routes"]
)


@router.get("")
def get_routes(db: Session = Depends(get_db)):
    routes = db.query(RouteORM).all()

    return [
        {
            "id": route.id,
            "name": route.name
        }
        for route in routes
    ]

@router.get("/search")
def search_routes(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    radius_m: int = 500,
    db: Session = Depends(get_db)
):
    start_point = func.ST_SetSRID(
        func.ST_MakePoint(start_lon, start_lat), 4326
    )

    end_point = func.ST_SetSRID(
        func.ST_MakePoint(end_lon, end_lat), 4326
    )

    routes = db.query(RouteORM).all()
    results = []

    for route in routes:
        start_near = db.scalar(
            db.query(
                func.ST_DWithin(
                    func.cast(RouteORM.geometry, Geography),
                    func.cast(start_point, Geography),
                    radius_m
                )
            ).filter(RouteORM.id == route.id).statement
        )

        end_near = db.scalar(
            db.query(
                func.ST_DWithin(
                    func.cast(RouteORM.geometry, Geography),
                    func.cast(end_point, Geography),
                    radius_m
                )
            ).filter(RouteORM.id == route.id).statement
        )

        if start_near and end_near:
            results.append(
                {
                    "route_id": route.id,
                    "name": route.name
                }
            )
    return {
        "count": len(results),
        "routes": results
    }

@router.get("/{route_id}")
def get_route(route_id: int, db: Session = Depends(get_db)):
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Route geometry as GeoJSON
    route_geojson_raw = db.scalar(
        db.query(func.ST_AsGeoJSON(RouteORM.geometry))
        .filter(RouteORM.id == route_id)
        .statement
    )

    if not route_geojson_raw:
        raise HTTPException(status_code=404, detail="Route geometry not found")

    route_geometry = json.loads(route_geojson_raw)

    # Stops
    stops_rows = (
        db.query(
            StopORM.id,
            StopORM.name,
            StopORM.stop_order,
            func.ST_AsGeoJSON(StopORM.location).label("geojson")
        )
        .filter(StopORM.route_id == route_id)
        .order_by(StopORM.stop_order)
        .all()
    )

    features = []

    # Add route line feature
    features.append(
        {
            "type": "Feature",
            "geometry": route_geometry,
            "properties": {
                "feature_type": "route",
                "route_id": route.id,
                "name": route.name
            }
        }
    )

    # Add stop point features
    for stop in stops_rows:
        stop_geometry = json.loads(stop.geojson) if stop.geojson else None

        features.append(
            {
                "type": "Feature",
                "geometry": stop_geometry,
                "properties": {
                    "feature_type": "stop",
                    "stop_id": stop.id,
                    "name": stop.name,
                    "order": stop.stop_order,
                    "route_id": route.id
                }
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.get("/{route_id}/stops")
def get_route_stops(route_id: int, db: Session = Depends(get_db)):
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stops = (
        db.query(StopORM)
        .filter(StopORM.route_id == route_id)
        .order_by(StopORM.stop_order)
        .all()
    )

    return {
        "route_id": route.id,
        "route_name": route.name,
        "stops": [
            {
                "id": stop.id,
                "name": stop.name,
                "stop_order": stop.stop_order
            }
            for stop in stops
        ]
    }


@router.get("/{route_id}/buses")
def get_route_buses(route_id: int):
    return {
        "route_id": route_id,
        "buses": [],
        "message": "Bus integration not implemented yet"
    }
