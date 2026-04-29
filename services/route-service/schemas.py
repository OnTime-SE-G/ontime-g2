from pydantic import BaseModel


class RouteOut(BaseModel):
    id: int
    name: str


class StopOut(BaseModel):
    id: int
    name: str
    order: int
    lat: float
    lng: float