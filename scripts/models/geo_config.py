from pydantic import BaseModel


class CoordinateBounds(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    def contains(self, *, lat: float, lon: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lon <= lon <= self.max_lon


SRI_LANKA_BOUNDS = CoordinateBounds(
    min_lat=5.85,
    max_lat=9.95,
    min_lon=79.4,
    max_lon=81.95,
)
