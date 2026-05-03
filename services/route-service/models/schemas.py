from pydantic import BaseModel
from typing import List, Optional


class StopResponse(BaseModel):
    id: int
    name: str
    stop_order: int
    lat: Optional[float] = None
    lon: Optional[float] = None

    model_config = {"from_attributes": True}


class RouteResponse(BaseModel):
    id: int
    name: str
    stops: List[StopResponse] = []

    model_config = {"from_attributes": True}


class BusResponse(BaseModel):
    id: int
    fleet_code: str
    plate_number: str
    capacity: int
    status: str
    route_id: int

    model_config = {"from_attributes": True}
