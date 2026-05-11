from datetime import date, time, datetime
from pydantic import BaseModel, ConfigDict, Field


class FleetBusCreate(BaseModel):
    fleet_code: str
    plate_number: str
    capacity: int = Field(default=50, gt=0)
    status: str = "active"


class FleetBusResponse(BaseModel):
    id: int
    fleet_code: str
    plate_number: str
    capacity: int
    status: str
    route_id: int | None

    model_config = ConfigDict(from_attributes=True)


class DeviceConfigCreate(BaseModel):
    location_interval: int | None = Field(default=None, ge=1000, le=60000)
    heartbeat_interval: int | None = Field(default=None, ge=10000, le=300000)
    new_bus_id: str | None = Field(default=None, min_length=1, max_length=15)


class DriverBase(BaseModel):
    name: str
    license_number: str
    phone: str | None = None


class DriverCreate(DriverBase):
    auth_user_id: str | None = None
    username: str | None = None


class DriverUpdate(BaseModel):
    """Partial update schema — only provided fields will be changed."""
    name: str | None = None
    license_number: str | None = None
    phone: str | None = None


class DriverResponse(DriverBase):
    id: int
    auth_user_id: str | None = None
    username: str | None = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ScheduleBase(BaseModel):
    route_id: int
    scheduled_time: time
    day_of_week: int  # 0-6


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleResponse(ScheduleBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PlannedTripResponse(BaseModel):
    id: str
    schedule_id: int
    bus_id: int | None
    driver_id: int | None
    date: date
    status: str
    
    # New fields
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    delay_minutes: int = 0
    last_incident_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PlannedTripCreate(BaseModel):
    schedule_id: int
    date: date
    bus_id: int | None = None
    driver_id: int | None = None


class TripDelayReport(BaseModel):
    delay_minutes: int = Field(..., gt=-1440, lt=1440)


class TripIncidentReport(BaseModel):
    incident_type: str = Field(..., description="BREAKDOWN, ACCIDENT, HEAVY_TRAFFIC, ROAD_CLOSURE, MEDICAL_EMERGENCY")
    message: str | None = None


class TripLifecycleResponse(BaseModel):
    trip_id: str
    status: str
    message: str
