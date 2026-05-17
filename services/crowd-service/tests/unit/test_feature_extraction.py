"""Unit tests for feature extraction."""

import pytest
from datetime import datetime
from app.routers.predictions import _extract_features_from_request, _map_crowd_count_to_level
from app.models import CrowdPredictionRequest


def test_extract_features_morning_rush():
    """Test feature extraction for morning rush hour."""
    req = CrowdPredictionRequest(
        timestamp=datetime(2023, 10, 24, 8, 15, 0),  # 8 AM, Tuesday
        vehicle_id="BUS_001",
        trip_id="TRIP_123",
        route_id="ROUTE_45",
        stop_id="Stop_A",
        dwell_prev_sec=45,
        dwell_current_sec=120
    )
    
    features = _extract_features_from_request(req)
    
    # Should have 6 features: [hour, day_of_week, is_weekend, is_holiday, dwell_prev, dwell_current]
    assert len(features) == 6
    assert features[0] == 8  # hour
    assert features[1] == 1  # Tuesday (0=Monday)
    assert features[2] == 0  # not weekend
    assert features[3] == 0  # not holiday
    assert features[4] == 45  # dwell_prev_sec
    assert features[5] == 120  # dwell_current_sec


def test_extract_features_weekend():
    """Test feature extraction for weekend."""
    req = CrowdPredictionRequest(
        timestamp=datetime(2023, 10, 28, 14, 30, 0),  # Saturday
        vehicle_id="BUS_002",
        trip_id="TRIP_124",
        route_id="ROUTE_45",
        stop_id="Stop_B",
        dwell_prev_sec=30,
        dwell_current_sec=60
    )
    
    features = _extract_features_from_request(req)
    
    assert features[1] == 5  # Saturday
    assert features[2] == 1  # is_weekend = True


def test_map_crowd_count_to_level_low():
    """Test crowd level mapping for low counts."""
    level = _map_crowd_count_to_level(10)
    assert level == "Low"
    
    level = _map_crowd_count_to_level(19)
    assert level == "Low"


def test_map_crowd_count_to_level_medium():
    """Test crowd level mapping for medium counts."""
    level = _map_crowd_count_to_level(20)
    assert level == "Medium"
    
    level = _map_crowd_count_to_level(49)
    assert level == "Medium"


def test_map_crowd_count_to_level_high():
    """Test crowd level mapping for high counts."""
    level = _map_crowd_count_to_level(50)
    assert level == "High"
    
    level = _map_crowd_count_to_level(100)
    assert level == "High"
