from datetime import date
from typing import List, Any
from fastapi import APIRouter, HTTPException, Body
from httpx import HTTPStatusError

from app.services.fleet_client import (
    add_bus, update_bus, delete_bus, get_buses, get_bus, get_route_buses,
    assign_route, unassign_route,
    create_driver, list_drivers,
    create_schedule, list_schedules,
    generate_planned_trips, get_today_trips, get_trip_detail, assign_trip_resources,
    report_trip_delay, report_trip_incident
)
from app.schemas import (
    BusResponse, BusAssignmentResponse, BusDeletionResponse,
    DriverCreate, DriverResponse,
    ScheduleCreate, ScheduleResponse,
    PlannedTripResponse, TripDelayReport, TripIncidentReport
)

router = APIRouter(
    prefix="/api/v1/admin/fleet",
    tags=["Admin Fleet"],
    # NOTE for G4/Kong: All routes under this prefix require admin-level authentication.
)

# ── Bus Management ────────────────────────────────────────────────────────────

@router.post("/buses", response_model=BusResponse)
async def create_bus(bus_data: dict = Body(...)):
    """Register a new bus to the fleet. Admin only."""
    try:
        return await add_bus(bus_data)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.put("/buses/{bus_id}", response_model=BusResponse)
async def modify_bus(bus_id: str, bus_data: dict = Body(...)):
    """Update an existing bus's details. Admin only."""
    try:
        return await update_bus(bus_id, bus_data)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.delete("/buses/{bus_id}", response_model=BusDeletionResponse)
async def remove_bus(bus_id: str):
    """Remove a bus from the fleet. Admin only."""
    try:
        return await delete_bus(bus_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/buses", response_model=List[BusResponse])
async def get_all_buses():
    """List all buses in the fleet. Admin only."""
    try:
        return await get_buses()
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/buses/{bus_id}", response_model=BusResponse)
async def get_bus(bus_id: int):
    """Get details for a single bus. Admin only."""
    try:
        return await get_bus(bus_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/buses/route/{route_id}", response_model=List[BusResponse])
async def get_buses_by_route(route_id: int):
    """List all buses assigned to a specific route. Admin only."""
    try:
        return await get_route_buses(route_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/buses/{bus_id}/assign-route/{route_id}", response_model=BusAssignmentResponse)
async def assign_bus_to_route(bus_id: str, route_id: str):
    """Assign a bus to a route. Admin only."""
    try:
        return await assign_route(bus_id, route_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/buses/{bus_id}/unassign", response_model=BusAssignmentResponse)
async def unassign_bus(bus_id: str):
    """Unassign a bus from its current route. Admin only."""
    try:
        return await unassign_route(bus_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


# ── Driver Management ─────────────────────────────────────────────────────────

@router.post("/drivers", response_model=DriverResponse)
async def add_driver(driver: DriverCreate):
    """
    Register a new driver.

    Admin only. Accepts driver name, license number, and optional phone.
    """
    try:
        return await create_driver(driver.model_dump())
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/drivers", response_model=List[DriverResponse])
async def get_drivers():
    """
    List all registered drivers.

    Admin only. Returns driver profiles used in timetable assignment.
    """
    try:
        return await list_drivers()
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


# ── Schedule Management ───────────────────────────────────────────────────────

@router.post("/schedules", response_model=ScheduleResponse)
async def add_schedule(schedule: ScheduleCreate):
    """
    Create a recurring bus schedule template.

    Admin only. Defines a route + time slot + day of week. Daily planned trips
    are generated from these templates.

    Example payload:
        {"route_id": 1, "scheduled_time": "08:30:00", "day_of_week": 0}

    day_of_week: 0=Monday, 6=Sunday
    """
    try:
        # Convert time object to string for JSON serialization
        data = schedule.model_dump()
        data["scheduled_time"] = data["scheduled_time"].strftime("%H:%M:%S")
        return await create_schedule(data)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/schedules", response_model=List[ScheduleResponse])
async def get_schedules():
    """
    List all schedule templates.

    Admin only. Returns all recurring timetable templates.
    """
    try:
        return await list_schedules()
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


# ── Planned Trip Management ───────────────────────────────────────────────────

@router.post("/planned-trips/generate")
async def generate_trips(target_date: date):
    """
    Generate the daily trip list from schedules for a given date.

    Admin only. Creates one PlannedTrip record per Schedule that falls on
    the given day of week. Idempotent — calling twice on the same date
    does not create duplicates.
    """
    try:
        return await generate_planned_trips(str(target_date))
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/planned-trips/today", response_model=List[PlannedTripResponse])
async def today_trips():
    """
    Get today's full timetable.

    Admin only (admin view includes all trips and assigned resources).
    """
    try:
        return await get_today_trips()
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/planned-trips/{trip_id}", response_model=PlannedTripResponse)
async def get_trip(trip_id: str):
    """
    Get details of a specific planned trip.

    Admin only. Includes status, assigned bus, and driver.
    """
    try:
        return await get_trip_detail(trip_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.patch("/planned-trips/{trip_id}/assign", response_model=PlannedTripResponse)
async def assign_resources(trip_id: str, bus_id: int, driver_id: int):
    """
    Assign a bus and driver to a planned trip.

    Admin only. Must be done before the driver can start the trip.
    """
    try:
        return await assign_trip_resources(trip_id, bus_id, driver_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/planned-trips/{trip_id}/delay", response_model=PlannedTripResponse)
async def override_delay(trip_id: str, report: TripDelayReport):
    """
    Override or report a delay for a trip.

    Admin version of delay reporting.
    """
    try:
        return await report_trip_delay(trip_id, report.delay_minutes)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.post("/planned-trips/{trip_id}/incident", response_model=PlannedTripResponse)
async def log_incident(trip_id: str, report: TripIncidentReport):
    """
    Log an incident for a trip.

    Admin version of incident reporting.
    """
    try:
        return await report_trip_incident(trip_id, report.incident_type, report.message)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
