from fastapi import APIRouter, UploadFile, File, Depends, Form
from sqlalchemy.orm import Session

from app.database import get_db
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