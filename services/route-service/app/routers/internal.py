from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from app.database import get_db
from app.models.db_route import RouteORM

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
