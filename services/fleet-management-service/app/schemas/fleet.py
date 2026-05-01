from pydantic import BaseModel, ConfigDict, Field


class FleetBusCreate(BaseModel):
    fleet_code: str
    plate_number: str
    capacity: int = Field(default=50, gt=0)


class FleetBusResponse(BaseModel):
    id: int
    fleet_code: str
    plate_number: str
    capacity: int
    route_id: int | None

    model_config = ConfigDict(from_attributes=True)
