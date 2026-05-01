import json
from datetime import datetime, timezone

from services.ingestion.app.validator import validate_gps_location_payload, validate_gps_payload


def test_valid_gps_message():
    """1. Valid GPS message -> success=True, correct GPSMessage returned."""
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
    
    result = validate_gps_payload(raw_bytes)
    assert result.success is True
    assert result.message is not None
    assert result.message.bus_id == "BUS_001"
    assert result.location.bus_id == "BUS_001"
    assert result.message.lat == 6.9271


def test_valid_g1_location_message_without_trip_id():
    """G1 MQTT location payloads do not include tripId before enrichment."""
    payload = {
        "busId": "1",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "heading": 120.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw_bytes = json.dumps(payload).encode("utf-8")

    result = validate_gps_location_payload(raw_bytes)

    assert result.success is True
    assert result.location is not None
    assert result.message is None
    assert result.location.bus_id == "1"


def test_enriched_gps_message_still_requires_trip_id():
    """Raw Kafka GPSMessage remains enriched and requires tripId."""
    payload = {
        "busId": "1",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "heading": 120.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw_bytes = json.dumps(payload).encode("utf-8")

    result = validate_gps_payload(raw_bytes)

    assert result.success is False
    assert result.error_type == "SCHEMA_VALIDATION"
    assert "tripId" in result.error_reason or "trip_id" in result.error_reason


def test_invalid_json():
    """2. Invalid JSON -> error_type=JSON_PARSE."""
    raw_bytes = b"not a valid json { string"
    result = validate_gps_payload(raw_bytes)
    
    assert result.success is False
    assert result.error_type == "JSON_PARSE"
    assert "Failed to parse JSON" in result.error_reason


def test_missing_required_field():
    """3. Missing required field (no busId) -> error_type=SCHEMA_VALIDATION."""
    payload = {
        "tripId": "TRIP_001",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    
    result = validate_gps_payload(raw_bytes)
    assert result.success is False
    assert result.error_type == "SCHEMA_VALIDATION"
    assert "busId" in result.error_reason or "bus_id" in result.error_reason


def test_speed_exceeds_bounds():
    """4. Speed > 200 -> error_type=SCHEMA_VALIDATION."""
    payload = {
        "busId": "BUS_001",
        "tripId": "TRIP_001",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 250.0,  # Speed must be <= 200
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    
    result = validate_gps_payload(raw_bytes)
    assert result.success is False
    assert result.error_type == "SCHEMA_VALIDATION"
    assert "speed" in result.error_reason


def test_coordinates_in_europe():
    """5. Coordinates in Europe -> error_type=GEO_BOUNDS."""
    payload = {
        "busId": "BUS_001",
        "tripId": "TRIP_001",
        "lat": 48.8566,  # Paris
        "lon": 2.3522,
        "speed": 45.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    
    result = validate_gps_payload(raw_bytes)
    assert result.success is False
    assert result.error_type == "GEO_BOUNDS"
    assert "out of bounds" in result.error_reason


def test_coordinates_on_boundary_edge():
    """6. Coordinates on boundary edge (lat=5.85 exactly) -> success=True."""
    payload = {
        "busId": "BUS_001",
        "tripId": "TRIP_001",
        "lat": 5.85,    # Exact min_lat boundary for Sri Lanka
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    
    result = validate_gps_payload(raw_bytes)
    assert result.success is True
    assert result.message.lat == 5.85


def test_missing_timestamp_returns_specific_error_type():
    payload = {
        "busId": "BUS_001",
        "tripId": "TRIP_001",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
    }
    raw_bytes = json.dumps(payload).encode("utf-8")

    result = validate_gps_payload(raw_bytes)

    assert result.success is False
    assert result.error_type == "MISSING_TIMESTAMP"
    assert "timestamp" in result.error_reason
