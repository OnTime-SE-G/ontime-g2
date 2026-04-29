import json
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from services.ingestion.validator import StatefulValidator


def test_duplicate_message():
    """1. Same message twice -> second returns DUPLICATE."""
    validator = StatefulValidator()
    
    payload = {
        "busId": "BUS_001",
        "tripId": "TRIP_001",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "heading": 120.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    
    # First message should pass
    result1 = validator.validate(raw_bytes)
    assert result1.success is True
    
    # Second identical message should be DUPLICATE
    result2 = validator.validate(raw_bytes)
    assert result2.success is False
    assert result2.error_type == "DUPLICATE"


def test_rate_limit():
    """2. Two messages < 1 second apart -> second returns RATE_LIMIT."""
    validator = StatefulValidator()
    
    base_time = datetime.now(timezone.utc)
    
    payload1 = {
        "busId": "BUS_002",
        "tripId": "TRIP_002",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat()
    }
    
    payload2 = {
        "busId": "BUS_002",
        "tripId": "TRIP_002",
        "lat": 6.9280,  # Different location so hash is different
        "lon": 79.8620,
        "speed": 46.0,
        "timestamp": (base_time + timedelta(seconds=2)).isoformat()
    }
    
    # Mock time.monotonic to simulate rapid arrival
    with patch("services.ingestion.validator.time.monotonic") as mock_time:
        mock_time.return_value = 100.0
        
        # First message
        result1 = validator.validate(json.dumps(payload1).encode("utf-8"))
        assert result1.success is True
        
        # Second message arrives 0.5 seconds later (rate limited)
        mock_time.return_value = 100.5
        result2 = validator.validate(json.dumps(payload2).encode("utf-8"))
        assert result2.success is False
        assert result2.error_type == "RATE_LIMIT"


def test_out_of_order_sequence():
    """3. Out-of-order timestamp -> SEQUENCE_ERROR."""
    validator = StatefulValidator()
    
    base_time = datetime.now(timezone.utc)
    
    payload1 = {
        "busId": "BUS_003",
        "tripId": "TRIP_003",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat()
    }
    
    payload2 = {
        "busId": "BUS_003",
        "tripId": "TRIP_003",
        "lat": 6.9280,
        "lon": 79.8620,
        "speed": 46.0,
        # Timestamp is older than payload1
        "timestamp": (base_time - timedelta(seconds=10)).isoformat()
    }
    
    with patch("services.ingestion.validator.time.monotonic") as mock_time:
        mock_time.return_value = 100.0
        
        # First message
        result1 = validator.validate(json.dumps(payload1).encode("utf-8"))
        assert result1.success is True
        
        # Second message arrives after 2 seconds (so no rate limit), but is old data
        mock_time.return_value = 102.0
        result2 = validator.validate(json.dumps(payload2).encode("utf-8"))
        assert result2.success is False
        assert result2.error_type == "SEQUENCE_ERROR"


def test_independent_bus_state():
    """4. Messages from different buses don't interfere with each other's state."""
    validator = StatefulValidator()
    
    base_time = datetime.now(timezone.utc)
    
    # Bus A payload
    payload_a = {
        "busId": "BUS_A",
        "tripId": "TRIP_A",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat()
    }
    
    # Bus B payload
    payload_b = {
        "busId": "BUS_B",
        "tripId": "TRIP_B",
        "lat": 6.9280,
        "lon": 79.8620,
        "speed": 46.0,
        "timestamp": (base_time - timedelta(seconds=10)).isoformat()
    }
    
    with patch("services.ingestion.validator.time.monotonic") as mock_time:
        mock_time.return_value = 100.0
        
        # Bus A message
        result_a = validator.validate(json.dumps(payload_a).encode("utf-8"))
        assert result_a.success is True
        
        # Bus B message arrives instantly (0 seconds apart), but it's a different bus
        # Also its timestamp is older than Bus A, but it shouldn't matter
        result_b = validator.validate(json.dumps(payload_b).encode("utf-8"))
        assert result_b.success is True
