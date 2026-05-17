"""Shared pytest fixtures for crowd service tests."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_prediction_request():
    """Sample crowd prediction request."""
    return {
        "timestamp": datetime(2023, 10, 24, 8, 15, 0).isoformat(),
        "vehicle_id": "BUS_001",
        "trip_id": "TRIP_123",
        "route_id": "ROUTE_45",
        "stop_id": "Stop_A",
        "dwell_prev_sec": 45,
        "dwell_current_sec": 120
    }


@pytest.fixture
def sample_prediction_request_midday():
    """Sample midday prediction request (less crowded)."""
    return {
        "timestamp": datetime(2023, 10, 24, 12, 30, 0).isoformat(),
        "vehicle_id": "BUS_002",
        "trip_id": "TRIP_124",
        "route_id": "ROUTE_45",
        "stop_id": "Stop_C",
        "dwell_prev_sec": 15,
        "dwell_current_sec": 10
    }


@pytest.fixture
def sample_prediction_request_evening():
    """Sample evening prediction request (crowded)."""
    return {
        "timestamp": datetime(2023, 10, 24, 17, 45, 0).isoformat(),
        "vehicle_id": "BUS_003",
        "trip_id": "TRIP_125",
        "route_id": "ROUTE_45",
        "stop_id": "Stop_B",
        "dwell_prev_sec": 180,
        "dwell_current_sec": 90
    }
