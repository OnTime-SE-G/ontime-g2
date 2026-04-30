from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_bus import BusORM
from app.schemas.bus import BusCreate, BusResponse

router = APIRouter(
    prefix="/api/v1/buses",
    tags=["Buses"]
)


@router.post("", response_model=BusResponse)
def create_bus(bus: BusCreate, db: Session = Depends(get_db)):
    db_bus = BusORM(**bus.model_dump())
    db.add(db_bus)
    db.commit()
    db.refresh(db_bus)
    return db_bus


@router.get("", response_model=list[BusResponse])
def get_buses(db: Session = Depends(get_db)):
    return db.query(BusORM).all()


@router.get("/{bus_id}", response_model=BusResponse)
def get_bus(bus_id: int, db: Session = Depends(get_db)):
    bus = db.query(BusORM).filter(BusORM.id == bus_id).first()
    if not bus:
        raise HTTPException(404, "Bus not found")
    return bus


@router.get("/route/{route_id}", response_model=list[BusResponse])
def get_buses_by_route(route_id: int, db: Session = Depends(get_db)):
    return db.query(BusORM).filter(BusORM.route_id == route_id).all()