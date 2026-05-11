from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_fleet import FleetBusORM
from app.schemas.fleet import FleetBusCreate, FleetBusResponse, DeviceConfigCreate
from app.services.route_service import validate_route_exists
from app.services.kafka_producer import kafka_service

router = APIRouter(
    prefix="/api/v1/fleet/buses",
    tags=["Fleet Management"]
)


#Create a new bus
@router.post("", response_model=FleetBusResponse)
def create_bus(bus: FleetBusCreate, db: Session = Depends(get_db)):
    db_bus = FleetBusORM(**bus.model_dump())
    db.add(db_bus)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bus with this fleet_code or plate_number already exists",
        ) from exc

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


# Configure bus device
@router.put("/{bus_id}/config")
async def configure_bus(bus_id: int, config: DeviceConfigCreate, db: Session = Depends(get_db)):
    bus = db.query(FleetBusORM).filter(FleetBusORM.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    config_dict = config.model_dump(exclude_unset=True)
    if not config_dict:
        raise HTTPException(status_code=400, detail="No configuration provided")

    await kafka_service.publish_device_config(str(bus.id), config_dict)
    return {"status": "success", "message": "Configuration queued for delivery"}


# Assign bus to route
@router.patch("/{bus_id}/assign-route/{route_id}", response_model=FleetBusResponse)
def assign_route(bus_id: int, route_id: int, db: Session = Depends(get_db)):
    bus = db.query(FleetBusORM).filter(FleetBusORM.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    try:
        validate_route_exists(route_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Route validation failed") from exc

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
