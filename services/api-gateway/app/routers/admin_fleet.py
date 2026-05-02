from fastapi import APIRouter, HTTPException, Body
from httpx import HTTPStatusError

from app.services.fleet_client import (
    add_bus, update_bus, delete_bus, assign_route, unassign_route
)
from app.schemas import BusResponse, BusAssignmentResponse, BusDeletionResponse

router = APIRouter(
    prefix="/api/v1/admin/fleet",
    tags=["Admin Fleet"]
)

@router.post("/buses", response_model=BusResponse)
async def create_bus(bus_data: dict = Body(...)):
    """
    Register a new bus to the fleet.

    Accepts the bus details as JSON payload and returns the newly created bus information.
    """
    try:
        return await add_bus(bus_data)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router.put("/buses/{bus_id}", response_model=BusResponse)
async def modify_bus(bus_id: str, bus_data: dict = Body(...)):
    """
    Update the details of an existing bus.

    Accepts updated fields in a JSON payload and returns the updated bus data.
    """
    try:
        return await update_bus(bus_id, bus_data)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router.delete("/buses/{bus_id}", response_model=BusDeletionResponse)
async def remove_bus(bus_id: str):
    """
    Remove a bus from the fleet.

    Deletes the bus permanently and returns a confirmation message.
    """
    try:
        return await delete_bus(bus_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router.post("/buses/{bus_id}/assign-route/{route_id}", response_model=BusAssignmentResponse)
async def assign_bus_to_route(bus_id: str, route_id: str):
    """
    Assign a bus to a specific route.

    Marks the bus as active on the given route, updating its route allocation.
    """
    try:
        return await assign_route(bus_id, route_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

@router.post("/buses/{bus_id}/unassign", response_model=BusAssignmentResponse)
async def unassign_bus(bus_id: str):
    """
    Unassign a bus from its current route.

    Removes the active route assignment from the bus, placing it in an idle state.
    """
    try:
        return await unassign_route(bus_id)
    except HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
