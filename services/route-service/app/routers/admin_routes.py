from fastapi import APIRouter, UploadFile, File, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_route import RouteORM
from app.services.kml_service import import_kml_file

router = APIRouter(
    prefix="/api/v1/admin/routes",
    tags=["Admin Routes"]
)


@router.post("/add-route")
def upload_kml(
    route_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    return import_kml_file(file, route_name, db)


@router.put("/{route_id}")
def update_route(
    route_id: int,
    route_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # remove old route first (stops cascade delete)
    db.delete(route)
    db.commit()

    # recreate from uploaded KML
    return import_kml_file(file, route_name, db)


@router.delete("/{route_id}")
def delete_route(
    route_id: int,
    db: Session = Depends(get_db)
):
    route = db.query(RouteORM).filter(RouteORM.id == route_id).first()

    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    db.delete(route)
    db.commit()

    return {
        "message": "Route deleted successfully",
        "route_id": route_id
    }