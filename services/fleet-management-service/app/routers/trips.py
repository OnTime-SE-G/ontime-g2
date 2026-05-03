from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db_fleet import DriverORM, ScheduleORM, PlannedTripORM
from app.schemas.fleet import (
    DriverCreate, DriverResponse, 
    ScheduleCreate, ScheduleResponse,
    PlannedTripResponse, PlannedTripCreate,
    TripLifecycleResponse, TripDelayReport, TripIncidentReport
)
from app.services import trip_service
from app.services.route_service import validate_route_exists

router = APIRouter(
    prefix="/api/v1/fleet",
    tags=["Trip Management"]
)

# --- Drivers ---

@router.post("/drivers", response_model=DriverResponse)
def create_driver(driver: DriverCreate, db: Session = Depends(get_db)):
    db_driver = DriverORM(**driver.model_dump())
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver

@router.get("/drivers", response_model=List[DriverResponse])
def get_drivers(db: Session = Depends(get_db)):
    return db.query(DriverORM).all()

# --- Schedules ---

@router.post("/schedules", response_model=ScheduleResponse)
def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    # Validate route exists in route-service
    validate_route_exists(schedule.route_id)
    
    db_schedule = ScheduleORM(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@router.get("/schedules", response_model=List[ScheduleResponse])
def get_schedules(db: Session = Depends(get_db)):
    return db.query(ScheduleORM).all()

# --- Planned Trips ---

@router.post("/planned-trips/generate")
async def trigger_generation(target_date: date, db: Session = Depends(get_db)):
    return await trip_service.generate_daily_trips(db, target_date)

@router.get("/planned-trips/today", response_model=List[PlannedTripResponse])
def get_today_trips(db: Session = Depends(get_db)):
    today = date.today()
    return db.query(PlannedTripORM).filter(PlannedTripORM.date == today).all()

@router.get("/planned-trips/{trip_id}", response_model=PlannedTripResponse)
def get_trip_detail(trip_id: str, db: Session = Depends(get_db)):
    trip = db.query(PlannedTripORM).filter(PlannedTripORM.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip

@router.patch("/planned-trips/{trip_id}/assign")
def assign_resources(trip_id: str, bus_id: int, driver_id: int, db: Session = Depends(get_db)):
    trip = db.query(PlannedTripORM).filter(PlannedTripORM.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    trip.bus_id = bus_id
    trip.driver_id = driver_id
    db.commit()
    db.refresh(trip)
    return trip

@router.post("/planned-trips/{trip_id}/start", response_model=PlannedTripResponse)
async def api_start_trip(trip_id: str, db: Session = Depends(get_db)):
    return await trip_service.start_trip(db, trip_id)

@router.post("/planned-trips/{trip_id}/end", response_model=PlannedTripResponse)
async def api_end_trip(trip_id: str, db: Session = Depends(get_db)):
    return await trip_service.end_trip(db, trip_id)

@router.post("/planned-trips/{trip_id}/delay", response_model=PlannedTripResponse)
async def api_report_delay(trip_id: str, report: TripDelayReport, db: Session = Depends(get_db)):
    """Report a delay in minutes (positive for delay, negative for ahead)."""
    return await trip_service.report_delay(db, trip_id, report.delay_minutes)

@router.post("/planned-trips/{trip_id}/incident", response_model=PlannedTripResponse)
async def api_report_incident(trip_id: str, report: TripIncidentReport, db: Session = Depends(get_db)):
    """Report an incident (breakdown, accident, etc.)."""
    return await trip_service.report_incident(db, trip_id, report.incident_type, report.message)
