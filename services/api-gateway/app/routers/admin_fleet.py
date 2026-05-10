from datetime import date
from typing import List, Any
from fastapi import APIRouter, HTTPException, Body
from httpx import HTTPStatusError

from app.services.fleet_client import (
    add_bus, update_bus, delete_bus, get_buses, get_bus as get_bus_from_fleet
    , get_route_buses,
    assign_route, unassign_route,
    create_driver, get_driver as get_driver_from_fleet, update_driver as update_driver_in_fleet,
    list_drivers, deactivate_driver,
    create_schedule, list_schedules,
    generate_planned_trips, get_today_trips, get_trips, get_trip_detail, assign_trip_resources,
    report_trip_delay, report_trip_incident
)
from app.services.keycloak_client import keycloak_client
from app.schemas import (
    BusResponse, BusAssignmentResponse, BusDeletionResponse,
    AdminDriverCreate, DriverResponse, DriverUpdate, DriverDeactivationResponse,
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
        return await get_bus_from_fleet(bus_id)
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
async def add_driver(driver: AdminDriverCreate):
    """
    Register a new driver in both Keycloak and Fleet Management.

    Admin only. Accepts driver name, license number, optional phone, username, and password.
    """
    # 1. Create user in Keycloak
    auth_user_id = keycloak_client.create_user(
        username=driver.username,
        password=driver.password,
        first_name=driver.name.split()[0], # Best effort name split
        last_name=" ".join(driver.name.split()[1:]) if len(driver.name.split()) > 1 else "",
        role="DRIVER"
    )

    # 2. Create driver profile in Fleet Management
    fleet_payload = driver.model_dump(exclude={"password"})
    fleet_payload["auth_user_id"] = auth_user_id

    try:
        return await create_driver(fleet_payload)
    except HTTPStatusError as e:
        # Compensation: Rollback Keycloak user if Fleet creation fails
        try:
            keycloak_client.keycloak_admin.delete_user(auth_user_id)
        except Exception:
            pass # We tried our best
        raise HTTPException(status_code=e.response.status_code, detail=f"Fleet driver creation failed: {e.response.text}")
    except Exception as e:
        # Compensation: Rollback
        try:
            keycloak_client.keycloak_admin.delete_user(auth_user_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/drivers/{driver_id}/deactivate", response_model=DriverDeactivationResponse)
async def deactivate_driver_account(driver_id: int):
    """
    Soft-deactivate a driver in Fleet Management and disable their Keycloak account.
    
    Admin only.
    """
    try:
        # 1. Fetch current driver from fleet to get auth_user_id (to ensure it exists)
        # Note: we might need a get_driver endpoint in fleet, but we can just blindly
        # call the fleet deactivate endpoint which returns the updated driver profile.
        fleet_response = await deactivate_driver(driver_id)
        
        # 2. Disable in Keycloak if they have a linked identity
        auth_user_id = fleet_response.get("auth_user_id")
        if auth_user_id:
            keycloak_client.disable_user(auth_user_id)
            
        return {
            "id": driver_id,
            "auth_user_id": auth_user_id,
            "is_active": fleet_response.get("is_active", False),
            "message": "Driver deactivated successfully"
        }
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.get("/drivers/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: int):
    """
    Get details of a single driver by their fleet ID.

    Admin only.
    """
    try:
        return await get_driver_from_fleet(driver_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


@router.patch("/drivers/{driver_id}", response_model=DriverResponse)
async def edit_driver(driver_id: int, update: DriverUpdate):
    """
    Update a driver's profile fields (name, license_number, phone).

    Admin only. Does not affect Keycloak credentials.
    """
    try:
        return await update_driver_in_fleet(driver_id, update.model_dump(exclude_none=True))
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

@router.get("/planned-trips", response_model=List[PlannedTripResponse])
async def query_trips(
    target_date: date | None = None,
    driver_id: int | None = None,
    status: str | None = None,
):
    """
    Query planned trips with optional filters.

    Admin only. Supports filtering by date, driver, and trip status.
    Example: GET /planned-trips?target_date=2026-05-10&driver_id=4&status=EN_ROUTE
    """
    try:
        return await get_trips(
            target_date=str(target_date) if target_date else None,
            driver_id=driver_id,
            status=status,
        )
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


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
