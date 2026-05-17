"""Pydantic models for Crowd Prediction Service."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class CrowdPredictionRequest(BaseModel):
    """Input schema for crowd prediction."""
    
    timestamp: datetime = Field(..., description="ISO8601 timestamp of the prediction")
    vehicle_id: str = Field(..., description="Unique vehicle identifier")
    trip_id: str = Field(..., description="Unique trip identifier")
    route_id: str = Field(..., description="Route identifier")
    stop_id: str = Field(..., description="Current stop ID")
    dwell_prev_sec: int = Field(default=0, description="Dwell time at previous stop in seconds")
    dwell_current_sec: int = Field(default=0, description="Dwell time at current stop in seconds")


class CrowdPredictionResponse(BaseModel):
    """Output schema for crowd prediction."""
    
    vehicle_id: str = Field(..., description="Vehicle ID")
    trip_id: str = Field(..., description="Trip ID")
    stop_id: str = Field(..., description="Stop ID")
    timestamp: datetime = Field(..., description="Prediction timestamp")
    crowd_count: int = Field(..., description="Predicted passenger count")
    crowd_level: Literal["Low", "Medium", "High"] = Field(..., description="Crowd category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence (0-1)")


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service status")
    service_name: str = Field(..., description="Name of the service")
    version: str = Field(..., description="Service version")


class MetricsResponse(BaseModel):
    """Metrics response."""
    
    total_predictions: int = Field(..., description="Total predictions made")
    average_confidence: float = Field(..., description="Average model confidence")
    prediction_latency_ms: float = Field(..., description="Average prediction latency in milliseconds")


__all__ = [
    "CrowdPredictionRequest",
    "CrowdPredictionResponse",
    "HealthResponse",
    "MetricsResponse",
]
