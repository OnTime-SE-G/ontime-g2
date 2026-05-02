# services/api-gateway/routers/buses.py
# REST endpoints for bus data (Issue #20 — ORM SELECT layer).

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from services.route_service import get_bus, list_buses

router = APIRouter(prefix="/api/v1/buses", tags=["buses"])


def _bus_to_dict(bus) -> Dict[str, Any]:
    return {
        "id": bus.id,
        "fleet_code": bus.fleet_code,
        "plate_number": bus.plate_number,
        "capacity": bus.capacity,
        "status": bus.status,
        "route_id": bus.route_id,
    }


@router.get("", response_model=List[Dict[str, Any]])
def get_buses(db: Session = Depends(get_db)):
    """List all buses."""
    return [_bus_to_dict(b) for b in list_buses(db)]


@router.get("/{bus_id}", response_model=Dict[str, Any])
def get_bus_by_id(bus_id: int, db: Session = Depends(get_db)):
    """Get a single bus by ID."""
    bus = get_bus(db, bus_id)
    if bus is None:
        raise HTTPException(status_code=404, detail=f"Bus {bus_id} not found")
    return _bus_to_dict(bus)
