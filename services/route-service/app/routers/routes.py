#services/route-service/app/routers/routes.py

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2 import Geography
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from app.database import get_db
from app.models.db_route import RouteORM, StopORM, RouteStopLinkORM
from app.schemas import (
    RouteBusesResponse,
    RouteGeoJSONResponse,
    RouteProgressResponse,
    RouteSearchResponse,
    RouteStopsResponse,
    RouteSummary,
    StopAggregatedResponse,
    StopNearbyResponse
)
from sqlalchemy.orm import aliased

router = APIRouter(
    prefix="/api/v1",
    tags=["Routes & Stops"]
)

@router.get("/routes", response_model=list[RouteSummary])
def get_routes(db: Session = Depends(get_db)):
    """
    List all available routes.

    Returns each route with its ID, display name, route number, color, and destination.
    Geometry and stop details are intentionally omitted from this list response.
    """
    routes = db.query(RouteORM).order_by(RouteORM.id).all()
    return [
        {
            "id": route.id,
            "name": route.name,
            "route_number": route.route_number,
            "color": route.color,
            "destination": route.destination
        }
        for route in routes
    ]

@router.get("/routes/search", response_model=RouteSearchResponse)
def search_routes(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    radius_m: int = 500,
    db: Session = Depends(get_db)
):
    """
    Search for routes near both a start point and an end point.

    Finds all bus stops within the given radius (in meters) of both the start and end coordinates.
    Then, it identifies routes that connect a nearby start stop to a nearby end stop in the correct
    direction of travel (i.e., start stop comes before the end stop). Returns the matching routes
    along with exact board and alight stop IDs.
    """
    start_point = func.ST_SetSRID(func.ST_MakePoint(start_lon, start_lat), 4326)
    end_point = func.ST_SetSRID(func.ST_MakePoint(end_lon, end_lat), 4326)

    start_stops = db.query(StopORM).filter(
        func.ST_DWithin(func.cast(StopORM.location, Geography), func.cast(start_point, Geography), radius_m)
    ).all()

    end_stops = db.query(StopORM).filter(
        func.ST_DWithin(func.cast(StopORM.location, Geography), func.cast(end_point, Geography), radius_m)
    ).all()

    start_stop_ids = [s.id for s in start_stops]
    end_stop_ids = [s.id for s in end_stops]

    if not start_stop_ids or not end_stop_ids:
        return {"count": 0, "routes": []}

    StartLink = aliased(RouteStopLinkORM)
    EndLink = aliased(RouteStopLinkORM)

    valid_connections = (
        db.query(
            RouteORM,
            StartLink.stop_id.label("start_stop_id"),
            EndLink.stop_id.label("end_stop_id")
        )
        .join(StartLink, RouteORM.id == StartLink.route_id)
        .join(EndLink, RouteORM.id == EndLink.route_id)
        .filter(
            StartLink.stop_id.in_(start_stop_ids),
            EndLink.stop_id.in_(end_stop_ids),
            StartLink.stop_order < EndLink.stop_order
        )
        .all()
    )

    stop_names = {s.id: s.name for s in start_stops + end_stops}
    results = []
    seen_routes = set()

    for route, start_stop_id, end_stop_id in valid_connections:
        if route.id in seen_routes:
            continue
        seen_routes.add(route.id)

        results.append({
            "route_id": route.id,
            "name": route.name,
            "route_number": route.route_number,
            "color": route.color,
            "start_stop_id": start_stop_id,
            "start_stop_name": stop_names[start_stop_id],
            "end_stop_id": end_stop_id,
            "end_stop_name": stop_names[end_stop_id]
        })
            
    return {"count": len(results), "routes": results}

@router.get("/routes/{route_id}/progress", response_model=RouteProgressResponse)
def get_route_progress(
    route_id: int,
    lat: float,
    lon: float,
    target_stop_order: int,
    db: Session = Depends(get_db)
):
    """
    Calculate bus progress along a route toward a target stop.

    The provided latitude and longitude represent the current bus position.
    The endpoint validates that the position is close to the route, then
    returns travelled distance, remaining distance, total distance to the
    target stop, and progress percentage.
    """
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    link = (
        db.query(RouteStopLinkORM)
        .filter(RouteStopLinkORM.route_id == route_id, RouteStopLinkORM.stop_order == target_stop_order)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Target stop not found")
        
    stop = db.query(StopORM).filter(StopORM.id == link.stop_id).first()

    bus_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

    near_route = db.scalar(
        db.query(
            func.ST_DWithin(func.cast(RouteORM.geometry, Geography), func.cast(bus_point, Geography), 100)
        ).filter(RouteORM.id == route_id).statement
    )

    if not near_route:
        raise HTTPException(status_code=400, detail="Coordinate is too far from route")

    bus_frac = db.scalar(
        db.query(func.ST_LineLocatePoint(RouteORM.geometry, bus_point)).filter(RouteORM.id == route_id).statement
    )

    stop_frac = db.scalar(
        db.query(func.ST_LineLocatePoint(RouteORM.geometry, StopORM.location))
        .filter(RouteORM.id == route_id, StopORM.id == stop.id).statement
    )

    travelled_m = db.scalar(
        db.query(
            func.ST_Length(func.cast(func.ST_LineSubstring(RouteORM.geometry, 0, bus_frac), Geography))
        ).filter(RouteORM.id == route_id).statement
    )

    if bus_frac >= stop_frac:
        remaining_m = 0
    else:
        remaining_m = db.scalar(
            db.query(
                func.ST_Length(func.cast(func.ST_LineSubstring(RouteORM.geometry, bus_frac, stop_frac), Geography))
            ).filter(RouteORM.id == route_id).statement
        )

    total_to_target_m = travelled_m + remaining_m
    progress_pct = (travelled_m / total_to_target_m) * 100 if total_to_target_m > 0 else 0

    return {
        "route_id": route_id,
        "target_stop_order": target_stop_order,
        "target_stop_name": stop.name,
        "travelled_m": round(travelled_m, 2),
        "remaining_m": round(remaining_m, 2),
        "total_to_target_m": round(total_to_target_m, 2),
        "progress_pct": round(progress_pct, 2)
    }

@router.get("/routes/{route_id}", response_model=RouteGeoJSONResponse)
def get_route(route_id: int, db: Session = Depends(get_db)):
    """
    Get a route with geometry and stop locations as GeoJSON.

    Returns a GeoJSON FeatureCollection containing one route LineString feature
    and Point features for the route stops. Returns 404 when the route or its
    geometry cannot be found.
    """
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    route_geojson_raw = db.scalar(
        db.query(func.ST_AsGeoJSON(RouteORM.geometry)).filter(RouteORM.id == route_id).statement
    )
    if not route_geojson_raw:
        raise HTTPException(status_code=404, detail="Route geometry not found")

    route_geometry = json.loads(route_geojson_raw)

    stops_rows = (
        db.query(
            StopORM.id,
            StopORM.name,
            RouteStopLinkORM.stop_order,
            func.ST_AsGeoJSON(StopORM.location).label("geojson")
        )
        .join(RouteStopLinkORM, StopORM.id == RouteStopLinkORM.stop_id)
        .filter(RouteStopLinkORM.route_id == route_id)
        .order_by(RouteStopLinkORM.stop_order)
        .all()
    )

    features = [{
        "type": "Feature",
        "geometry": route_geometry,
        "properties": {
            "feature_type": "route",
            "route_id": route.id,
            "name": route.name,
            "route_number": route.route_number,
            "color": route.color
        }
    }]

    for stop in stops_rows:
        stop_geometry = json.loads(stop.geojson) if stop.geojson else None
        features.append({
            "type": "Feature",
            "geometry": stop_geometry,
            "properties": {
                "feature_type": "stop",
                "stop_id": stop.id,
                "name": stop.name,
                "order": stop.stop_order,
                "route_id": route.id
            }
        })

    return {"type": "FeatureCollection", "features": features}

@router.get("/routes/{route_id}/stops", response_model=RouteStopsResponse)
def get_route_stops(route_id: int, db: Session = Depends(get_db)):
    """
    List stops for a route in stop order.

    Returns route metadata and an ordered list of stops with ID, name, and stop
    order. Returns 404 when the route ID does not exist.
    """
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stops = (
        db.query(StopORM, RouteStopLinkORM.stop_order)
        .join(RouteStopLinkORM, StopORM.id == RouteStopLinkORM.stop_id)
        .filter(RouteStopLinkORM.route_id == route_id)
        .order_by(RouteStopLinkORM.stop_order)
        .all()
    )

    return {
        "route_id": route.id,
        "route_name": route.name,
        "stops": [{"id": stop.id, "name": stop.name, "stop_order": stop_order} for stop, stop_order in stops]
    }

@router.get("/routes/{route_id}/buses", response_model=RouteBusesResponse)
def get_route_buses(route_id: int, db: Session = Depends(get_db)):
    """
    List buses currently assigned to a route.

    This endpoint is a placeholder for future live bus integration. It returns
    an empty bus list until bus tracking data is connected.
    """
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return {"route_id": route_id, "buses": [], "message": "Bus integration not implemented yet"}

# --- New Stop Endpoints ---

@router.get("/stops/nearby", response_model=list[StopNearbyResponse])
def get_nearby_stops(
    lat: float, 
    lon: float, 
    radius_m: int = 500, 
    db: Session = Depends(get_db)
):
    """
    Find bus stops near a specific coordinate.

    Uses spatial proximity to find all stops within the given radius (in meters) of the
    provided latitude and longitude. Returns the stops sorted from nearest to farthest,
    including the exact distance in meters and the array of routes serving each stop.
    """
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

    stops_with_dist = (
        db.query(
            StopORM,
            func.ST_Distance(func.cast(StopORM.location, Geography), func.cast(point, Geography)).label("distance"),
            func.ST_AsGeoJSON(StopORM.location).label("geojson")
        )
        .filter(
            func.ST_DWithin(func.cast(StopORM.location, Geography), func.cast(point, Geography), radius_m)
        )
        .order_by("distance")
        .all()
    )

    result = []
    for stop, distance, geojson in stops_with_dist:
        links = db.query(RouteORM).join(RouteStopLinkORM).filter(RouteStopLinkORM.stop_id == stop.id).all()
        routes = [r.route_number if r.route_number else r.name for r in links]
        
        geometry = json.loads(geojson) if geojson else None
        coords = geometry["coordinates"] if geometry else None
        
        result.append({
            "id": stop.id,
            "name": stop.name,
            "coordinates": coords,
            "distance_m": round(distance, 1),
            "routes": routes
        })

    return result

@router.get("/stops", response_model=list[StopAggregatedResponse])
def get_all_stops(db: Session = Depends(get_db)):
    """
    List all deduplicated bus stops across the entire network.

    Retrieves all unique physical stops and aggregates the routes that pass through them.
    Used by the frontend to display the master list of all stops on the map.
    """
    stops = db.query(StopORM, func.ST_AsGeoJSON(StopORM.location).label("geojson")).all()
    
    result = []
    for stop, geojson in stops:
        # Get routes serving this stop
        links = db.query(RouteORM).join(RouteStopLinkORM).filter(RouteStopLinkORM.stop_id == stop.id).all()
        # Fallback to route name if route_number is not yet set
        routes = [r.route_number if r.route_number else r.name for r in links]
        
        geometry = json.loads(geojson) if geojson else None
        coords = geometry["coordinates"] if geometry else None
        
        result.append({
            "id": stop.id,
            "name": stop.name,
            "coordinates": coords,
            "routes": routes
        })
        
    return result

@router.get("/stops/{stop_id}/routes", response_model=list[RouteSummary])
def get_routes_for_stop(stop_id: int, db: Session = Depends(get_db)):
    """
    Get all routes that pass through a specific bus stop.

    Given a stop ID, this endpoint looks up the many-to-many associations and returns
    a list of route summaries for all routes that service this physical stop.
    """
    stop = db.query(StopORM).filter(StopORM.id == stop_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
        
    routes = (
        db.query(RouteORM)
        .join(RouteStopLinkORM)
        .filter(RouteStopLinkORM.stop_id == stop_id)
        .all()
    )
    
    return [
        {
            "id": route.id,
            "name": route.name,
            "route_number": route.route_number,
            "color": route.color,
            "destination": route.destination
        }
        for route in routes
    ]
