from pydantic import BaseModel


class FleetBusCreate(BaseModel):
    fleet_code: str
    plate_number: str
    capacity: int = 50


class FleetBusResponse(BaseModel):
    id: int
    fleet_code: str
    plate_number: str
    capacity: int
    route_id: int | None

    class Config:
        from_attributes = True