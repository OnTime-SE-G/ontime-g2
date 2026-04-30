from pydantic import BaseModel


class BusCreate(BaseModel):
    fleet_code: str
    plate_number: str
    capacity: int = 50


class BusResponse(BaseModel):
    id: int
    fleet_code: str
    plate_number: str
    capacity: int
    status: str
    route_id: int | None

    class Config:
        from_attributes = True