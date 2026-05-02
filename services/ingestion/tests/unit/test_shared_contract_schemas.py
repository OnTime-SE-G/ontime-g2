from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.gps import GPSLocationMessage, GPSMessage
from schemas.heartbeat import HeartbeatMessage
from schemas.trip_lifecycle import TripLifecycleEvent


def test_gps_location_message_accepts_g1_payload_without_trip_id():
    message = GPSLocationMessage.model_validate(
        {
            "busId": "1",
            "lat": 6.9271,
            "lon": 79.8612,
            "speed": 35.0,
            "heading": 120.0,
            "timestamp": "2026-05-02T10:15:30Z",
        }
    )

    assert message.bus_id == "1"
    assert message.timestamp.tzinfo is not None


def test_gps_location_message_requires_timestamp():
    with pytest.raises(ValidationError) as exc_info:
        GPSLocationMessage.model_validate(
            {
                "busId": "1",
                "lat": 6.9271,
                "lon": 79.8612,
                "speed": 35.0,
                "heading": 120.0,
            }
        )

    assert "timestamp" in str(exc_info.value)


def test_gps_message_requires_trip_id_for_enriched_kafka_output():
    with pytest.raises(ValidationError) as exc_info:
        GPSMessage.model_validate(
            {
                "busId": "1",
                "lat": 6.9271,
                "lon": 79.8612,
                "speed": 35.0,
                "heading": 120.0,
                "timestamp": "2026-05-02T10:15:30Z",
            }
        )

    assert "tripId" in str(exc_info.value) or "trip_id" in str(exc_info.value)


def test_gps_message_has_required_trip_id_and_timestamp():
    message = GPSMessage(
        bus_id="1",
        trip_id="TRIP-001",
        lat=6.9271,
        lon=79.8612,
        speed=35.0,
        heading=120.0,
        timestamp=datetime.now(timezone.utc),
    )

    assert message.trip_id == "TRIP-001"


def test_trip_lifecycle_event_schema_matches_fleet_contract():
    event = TripLifecycleEvent.model_validate(
        {
            "event": "TRIP_STARTED",
            "busId": "1",
            "tripId": "TRIP-001",
            "routeId": "202",
            "timestamp": "2026-05-02T10:00:00Z",
        }
    )

    assert event.bus_id == "1"
    assert event.trip_id == "TRIP-001"
    assert event.route_id == "202"


def test_heartbeat_message_schema_matches_g1_device_status_contract():
    heartbeat = HeartbeatMessage.model_validate(
        {
            "busId": "1",
            "deviceId": "GPS-1",
            "timestamp": "2026-05-02T10:15:30Z",
            "gpsFix": True,
            "satellites": 8,
            "signalQuality": 21,
            "batteryVoltage": 3.9,
            "firmwareVersion": "g1-0.1.0",
        }
    )

    assert heartbeat.bus_id == "1"
    assert heartbeat.device_id == "GPS-1"
    assert heartbeat.gps_fix is True
    assert heartbeat.timestamp.tzinfo is not None
