from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class CrowdReportRequest(BaseModel):
    trip_id: str = Field(..., max_length=64)
    route_id: int
    direction_id: Optional[int] = None
    stop_id: int
    stop_sequence: Optional[int] = None
    occupancy_score: int = Field(..., ge=0, le=100)
    passenger_id: Optional[str] = Field(None, max_length=128)
    timestamp: datetime

class CrowdPredictionResponse(BaseModel):
    prediction: str
    confidence: float
    historical_prediction: str
    live_adjustment: bool
    live_report_count: int
    source: str
