from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models.orm import BusORM
from ..models.schemas import BusResponse

router = APIRouter(prefix="/buses", tags=["buses"])


@router.get("/", response_model=List[BusResponse])
def list_buses(db: Session = Depends(get_db)):
    return db.query(BusORM).all()


@router.get("/{bus_id}", response_model=BusResponse)
def get_bus(bus_id: int, db: Session = Depends(get_db)):
    bus = db.query(BusORM).filter(BusORM.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return bus
