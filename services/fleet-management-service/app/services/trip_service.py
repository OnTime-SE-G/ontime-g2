import uuid
import logging
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.db_fleet import PlannedTripORM, ScheduleORM, FleetBusORM, DriverORM, TripStatus, TripIncidentORM
from app.services.kafka_producer import kafka_service
from app.services.route_service import validate_route_exists
from schemas.trip_lifecycle import TripLifecycleEvent

logger = logging.getLogger(__name__)

async def generate_daily_trips(db: Session, target_date: date):
    """Generate PlannedTrip records from Schedules for a specific date."""
    day_of_week = target_date.weekday()
    
    # Check if trips already exist for this date
    existing = db.query(PlannedTripORM).filter(PlannedTripORM.date == target_date).first()
    if existing:
        return {"message": f"Trips for {target_date} already exist", "count": 0}

    schedules = db.query(ScheduleORM).filter(ScheduleORM.day_of_week == day_of_week).all()
    
    new_trips = []
    for schedule in schedules:
        trip_id = f"TRIP-{uuid.uuid4().hex[:8].upper()}"
        new_trip = PlannedTripORM(
            id=trip_id,
            schedule_id=schedule.id,
            date=target_date,
            status=TripStatus.WAITING_AT_DEPOT
        )
        db.add(new_trip)
        new_trips.append(new_trip)
    
    db.commit()
    return {"message": f"Generated {len(new_trips)} trips for {target_date}", "count": len(new_trips)}

async def start_trip(db: Session, trip_id: str):
    """Transition a planned trip to EN_ROUTE and notify the system."""
    trip = db.query(PlannedTripORM).filter(PlannedTripORM.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if trip.status != TripStatus.WAITING_AT_DEPOT:
        raise HTTPException(status_code=400, detail=f"Cannot start trip in status {trip.status}")
    
    if not trip.bus_id or not trip.driver_id:
        raise HTTPException(status_code=400, detail="Trip must have a bus and driver assigned before starting")

    bus = db.query(FleetBusORM).filter(FleetBusORM.id == trip.bus_id).first()
    schedule = db.query(ScheduleORM).filter(ScheduleORM.id == trip.schedule_id).first()

    # Transition status
    trip.status = TripStatus.EN_ROUTE
    trip.actual_start_time = datetime.now(timezone.utc)
    db.commit()

    # Publish Kafka event
    event = TripLifecycleEvent(
        event="TRIP_STARTED",
        bus_id=bus.fleet_code,
        trip_id=trip.id,
        route_id=str(schedule.route_id),
        timestamp=trip.actual_start_time
    )
    await kafka_service.publish_trip_event(event)
    
    return trip

async def end_trip(db: Session, trip_id: str):
    """Transition an active trip to ARRIVED_DESTINATION and notify the system."""
    trip = db.query(PlannedTripORM).filter(PlannedTripORM.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    if trip.status not in [TripStatus.EN_ROUTE, TripStatus.INCIDENT_REPORTED]:
        raise HTTPException(status_code=400, detail=f"Cannot end trip in status {trip.status}")

    bus = db.query(FleetBusORM).filter(FleetBusORM.id == trip.bus_id).first()
    schedule = db.query(ScheduleORM).filter(ScheduleORM.id == trip.schedule_id).first()

    # Transition status
    trip.status = TripStatus.ARRIVED_DESTINATION
    trip.actual_end_time = datetime.now(timezone.utc)
    db.commit()

    # Publish Kafka event
    event = TripLifecycleEvent(
        event="TRIP_ENDED",
        bus_id=bus.fleet_code,
        trip_id=trip.id,
        route_id=str(schedule.route_id),
        timestamp=trip.actual_end_time
    )
    await kafka_service.publish_trip_event(event)
    
    return trip

async def report_delay(db: Session, trip_id: str, delay_minutes: int):
    """Update the delay status of a trip."""
    trip = db.query(PlannedTripORM).filter(PlannedTripORM.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    trip.delay_minutes = delay_minutes
    db.commit()
    
    # We could also publish a KAFKA event here if the ETA service needs immediate push
    # For now, ETA service will see it in the next telemetry enrichment or by querying.
    
    return trip

async def report_incident(db: Session, trip_id: str, incident_type: str, message: str | None):
    """Record an incident and transition trip status."""
    trip = db.query(PlannedTripORM).filter(PlannedTripORM.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Create incident record
    incident = TripIncidentORM(
        trip_id=trip_id,
        incident_type=incident_type,
        message=message
    )
    db.add(incident)
    
    # Transition status
    trip.status = TripStatus.INCIDENT_REPORTED
    trip.last_incident_type = incident_type
    db.commit()
    
    # Publish Kafka event
    bus = db.query(FleetBusORM).filter(FleetBusORM.id == trip.bus_id).first()
    schedule = db.query(ScheduleORM).filter(ScheduleORM.id == trip.schedule_id).first()
    
    event = TripLifecycleEvent(
        event="INCIDENT_REPORTED",
        bus_id=bus.fleet_code if bus else "UNKNOWN",
        trip_id=trip.id,
        route_id=str(schedule.route_id) if schedule else "UNKNOWN",
        timestamp=datetime.now(timezone.utc)
    )
    await kafka_service.publish_trip_event(event)
    
    return trip
