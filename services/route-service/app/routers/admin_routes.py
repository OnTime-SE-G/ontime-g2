from fastapi import APIRouter, UploadFile, File, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_route import RouteORM
from app.schemas import RouteDeleteResponse, RouteImportResponse
from app.services.kml_service import import_kml_file

router = APIRouter(
    prefix="/api/v1/admin/routes",
    tags=["Admin Routes"]
)


@router.post("/add-route", response_model=RouteImportResponse)
def upload_kml(
    route_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Import a new route from an uploaded KML file.

    The uploaded KML must contain a LineString for the route path and at least
    two Point placemarks for stops. If a route with the same name already
    exists, it is replaced before the new route and stops are saved.
    """
    return import_kml_file(file, route_name, db)


@router.put("/{route_id}", response_model=RouteImportResponse)
def update_route(
    route_id: int,
    route_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Replace an existing route with data from a new KML upload.

    The existing route and its stops are deleted first, then the uploaded KML is
    imported as the replacement route. Returns 404 when the route ID does not
    exist.
    """
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # remove old route first (stops cascade delete)
    db.delete(route)
    db.commit()

    # recreate from uploaded KML
    return import_kml_file(file, route_name, db)


@router.delete("/{route_id}", response_model=RouteDeleteResponse)
def delete_route(
    route_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a route and its related stops.

    Removes the route identified by `route_id`. Related stops are removed by
    the model cascade. Returns 404 when the route ID does not exist.
    """
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    db.delete(route)
    db.commit()

    return {
        "message": "Route deleted successfully",
        "route_id": route_id
    }
