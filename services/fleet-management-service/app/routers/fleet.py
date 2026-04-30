from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_fleet import FleetBusORM
from app.schemas.fleet import FleetBusCreate, FleetBusResponse

router = APIRouter(
    prefix="/api/v1/fleet/buses",
    tags=["Fleet Management"]
)


#Create a new bus
@router.post("", response_model=FleetBusResponse)
def create_bus(bus: FleetBusCreate, db: Session = Depends(get_db)):
    db_bus = FleetBusORM(**bus.model_dump())
    db.add(db_bus)
    db.commit()
    db.refresh(db_bus)
    return db_bus


#Get all buses
@router.get("", response_model=list[FleetBusResponse])
def get_buses(db: Session = Depends(get_db)):
    return db.query(FleetBusORM).all()


#Get single bus
@router.get("/{bus_id}", response_model=FleetBusResponse)
def get_bus(bus_id: int, db: Session = Depends(get_db)):
    bus = db.query(FleetBusORM).filter(FleetBusORM.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return bus


# Assign bus to route
@router.patch("/{bus_id}/assign-route/{route_id}", response_model=FleetBusResponse)
def assign_route(bus_id: int, route_id: int, db: Session = Depends(get_db)):
    bus = db.query(FleetBusORM).filter(FleetBusORM.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    bus.route_id = route_id
    db.commit()
    db.refresh(bus)

    return bus


#Unassign route
@router.patch("/{bus_id}/unassign", response_model=FleetBusResponse)
def unassign_route(bus_id: int, db: Session = Depends(get_db)):
    bus = db.query(FleetBusORM).filter(FleetBusORM.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    setattr(bus, "route_id", None)
    db.commit()
    db.refresh(bus)

    return bus


#Get buses by route
@router.get("/route/{route_id}", response_model=list[FleetBusResponse])
def get_buses_by_route(route_id: int, db: Session = Depends(get_db)):
    return db.query(FleetBusORM).filter(FleetBusORM.route_id == route_id).all()