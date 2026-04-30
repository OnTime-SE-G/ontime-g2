from pydantic import BaseModel


class FleetBusCreate(BaseModel):
    fleet_code: str
    plate_number: str
    capacity: int = 50


from pydantic import BaseModel, ConfigDict


class FleetBusResponse(BaseModel):
    id: int
    fleet_code: str
    plate_number: str
    capacity: int
    route_id: int | None

    model_config = ConfigDict(from_attributes=True)