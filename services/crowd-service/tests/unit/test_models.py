"""Unit tests for the models module."""

import pytest
from datetime import datetime
from app.models import CrowdPredictionRequest, CrowdPredictionResponse


def test_crowd_prediction_request_valid():
    """Test valid crowd prediction request."""
    req = CrowdPredictionRequest(
        timestamp=datetime.now(),
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        route_id="ROUTE_45",
        stop_id="Stop_A",
        dwell_prev_sec=45,
        dwell_current_sec=120
    )
    
    assert req.vehicle_id == "BUS_001"
    assert req.dwell_current_sec == 120


def test_crowd_prediction_response_valid():
    """Test valid crowd prediction response."""
    resp = CrowdPredictionResponse(
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        stop_id="Stop_A",
        timestamp=datetime.now(),
        crowd_count=55,
        crowd_level="High",
        confidence=0.82
    )
    
    assert resp.crowd_count == 55
    assert resp.crowd_level == "High"
    assert resp.confidence == 0.82


def test_crowd_prediction_response_confidence_bounds():
    """Test confidence value bounds."""
    with pytest.raises(ValueError):
        CrowdPredictionResponse(
            vehicle_id="BUS_001",
            trip_id="TRIP_123",
            stop_id="Stop_A",
            timestamp=datetime.now(),
            crowd_count=55,
            crowd_level="High",
            confidence=1.5  # Invalid: > 1.0
        )
