from typing import Any, Literal, List, Optional
from pydantic import BaseModel

# --- Route Service Schemas ---

class RouteSummary(BaseModel):
    id: int
    name: str
    route_number: Optional[str] = None
    color: Optional[str] = None
    destination: Optional[str] = None

class RouteSearchResult(BaseModel):
    route_id: int
    name: str
    route_number: Optional[str] = None
    color: Optional[str] = None
    start_stop_id: int
    start_stop_name: str
    end_stop_id: int
    end_stop_name: str

class RouteSearchResponse(BaseModel):
    count: int
    routes: List[RouteSearchResult]

class RouteProgressResponse(BaseModel):
    route_id: int
    target_stop_order: int
    target_stop_name: str
    travelled_m: float
    remaining_m: float
    total_to_target_m: float
    progress_pct: float

class GeoJSONGeometry(BaseModel):
    type: str
    coordinates: Any

class RouteFeatureProperties(BaseModel):
    feature_type: Literal["route"]
    route_id: int
    name: str

class StopFeatureProperties(BaseModel):
    feature_type: Literal["stop"]
    stop_id: int
    name: str
    order: int
    route_id: int

class RouteFeature(BaseModel):
    type: Literal["Feature"]
    geometry: GeoJSONGeometry
    properties: RouteFeatureProperties

class StopFeature(BaseModel):
    type: Literal["Feature"]
    geometry: Optional[GeoJSONGeometry]
    properties: StopFeatureProperties

class RouteGeoJSONResponse(BaseModel):
    type: Literal["FeatureCollection"]
    features: List[Any]

class StopNearbyResponse(BaseModel):
    id: int
    name: str
    coordinates: Optional[List[float]] = None
    distance_m: float
    routes: List[str] = []

class StopAggregatedResponse(BaseModel):
    id: int
    name: str
    coordinates: Optional[List[float]] = None
    routes: List[str] = []

class StopSummary(BaseModel):
    id: int
    name: str
    stop_order: int

class RouteStopsResponse(BaseModel):
    route_id: int
    route_name: str
    stops: List[StopSummary]

class RouteBusesResponse(BaseModel):
    route_id: int
    buses: List[Any]
    message: str

class RouteImportResponse(BaseModel):
    message: str
    route_id: Optional[int] = None
    route_name: Optional[str] = None
    stops_inserted: Optional[int] = None

class RouteDeleteResponse(BaseModel):
    message: str
    route_id: int

# --- Fleet Service Schemas ---

class BusResponse(BaseModel):
    id: str
    fleet_code: str
    plate_number: str
    status: str
    route_id: Optional[str] = None
    capacity: Optional[int] = None

class LiveBusResponse(BaseModel):
    id: str
    fleet_code: str
    plate_number: str
    status: str
    route_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class BusAssignmentResponse(BaseModel):
    message: str
    bus_id: str
    route_id: Optional[str] = None

class BusDeletionResponse(BaseModel):
    message: str
    bus_id: str


# --- Timetable & Trip Schemas ---

from datetime import date, time, datetime

class DriverCreate(BaseModel):
    email: str
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    license_number: str
    phone: Optional[str] = None

class DriverResponse(BaseModel):
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None

class ScheduleCreate(BaseModel):
    route_id: int
    scheduled_time: time
    day_of_week: int

class ScheduleResponse(BaseModel):
    id: int
    route_id: int
    scheduled_time: time
    day_of_week: int

class PlannedTripResponse(BaseModel):
    id: str
    schedule_id: int
    bus_id: Optional[int] = None
    driver_id: Optional[str] = None
    date: date
    status: str
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    delay_minutes: int = 0
    last_incident_type: Optional[str] = None

class TripDelayReport(BaseModel):
    delay_minutes: int

class TripIncidentReport(BaseModel):
    incident_type: str
    message: Optional[str] = None

class TripLifecycleResponse(BaseModel):
    trip_id: str
    status: str
    message: str
