from typing import Any, Literal

from pydantic import BaseModel


class ServiceMetadataResponse(BaseModel):
    service: str
    status: str
    docs: str


class HealthResponse(BaseModel):
    status: str
    service: str


class RouteSummary(BaseModel):
    id: int
    name: str


class RouteSearchResult(BaseModel):
    route_id: int
    name: str


class RouteSearchResponse(BaseModel):
    count: int
    routes: list[RouteSearchResult]


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
    geometry: GeoJSONGeometry | None
    properties: StopFeatureProperties


class RouteGeoJSONResponse(BaseModel):
    type: Literal["FeatureCollection"]
    features: list[RouteFeature | StopFeature]


class StopSummary(BaseModel):
    id: int
    name: str
    stop_order: int


class RouteStopsResponse(BaseModel):
    route_id: int
    route_name: str
    stops: list[StopSummary]


class RouteBusesResponse(BaseModel):
    route_id: int
    buses: list[Any]
    message: str


class RouteImportResponse(BaseModel):
    message: str
    route_id: int
    route_name: str
    stops_inserted: int


class RouteDeleteResponse(BaseModel):
    message: str
    route_id: int
