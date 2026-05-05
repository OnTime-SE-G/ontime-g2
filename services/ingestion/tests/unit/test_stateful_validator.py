import json
from datetime import datetime, timedelta, timezone

from services.ingestion.app.validator import StatefulValidator


def test_duplicate_message():
    validator = StatefulValidator()
    payload = {
        "busId": "BUS_001",
        "tripId": "TRIP_001",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "heading": 120.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raw_bytes = json.dumps(payload).encode("utf-8")

    result1 = validator.validate(raw_bytes)
    assert result1.success is True

    result2 = validator.validate(raw_bytes)
    assert result2.success is False
    assert result2.error_type == "DUPLICATE"


def test_receive_time_burst_with_valid_event_times_is_accepted():
    validator = StatefulValidator()
    base_time = datetime.now(timezone.utc)

    payload1 = {
        "busId": "BUS_002",
        "tripId": "TRIP_002",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat(),
    }

    payload2 = {
        "busId": "BUS_002",
        "tripId": "TRIP_002",
        "lat": 6.9280,
        "lon": 79.8620,
        "speed": 46.0,
        "timestamp": (base_time + timedelta(seconds=2)).isoformat(),
    }

    result1 = validator.validate(json.dumps(payload1).encode("utf-8"))
    assert result1.success is True

    result2 = validator.validate(json.dumps(payload2).encode("utf-8"))
    assert result2.success is True


def test_event_time_rate_limit():
    validator = StatefulValidator(min_event_interval_seconds=1.0)
    base_time = datetime.now(timezone.utc)

    payload1 = {
        "busId": "BUS_002",
        "tripId": "TRIP_002",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat(),
    }

    payload2 = {
        "busId": "BUS_002",
        "tripId": "TRIP_002",
        "lat": 6.9280,
        "lon": 79.8620,
        "speed": 46.0,
        "timestamp": (base_time + timedelta(milliseconds=500)).isoformat(),
    }

    result1 = validator.validate(json.dumps(payload1).encode("utf-8"))
    assert result1.success is True

    result2 = validator.validate(json.dumps(payload2).encode("utf-8"))
    assert result2.success is False
    assert result2.error_type == "RATE_LIMIT_EVENT_TIME"


def test_out_of_order_sequence():
    validator = StatefulValidator()
    base_time = datetime.now(timezone.utc)

    payload1 = {
        "busId": "BUS_003",
        "tripId": "TRIP_003",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat(),
    }

    payload2 = {
        "busId": "BUS_003",
        "tripId": "TRIP_003",
        "lat": 6.9280,
        "lon": 79.8620,
        "speed": 46.0,
        "timestamp": (base_time - timedelta(seconds=10)).isoformat(),
    }

    result1 = validator.validate(json.dumps(payload1).encode("utf-8"))
    assert result1.success is True

    result2 = validator.validate(json.dumps(payload2).encode("utf-8"))
    assert result2.success is False
    assert result2.error_type == "SEQUENCE_ERROR"


def test_independent_bus_state():
    validator = StatefulValidator()
    base_time = datetime.now(timezone.utc)

    payload_a = {
        "busId": "BUS_A",
        "tripId": "TRIP_A",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat(),
    }

    payload_b = {
        "busId": "BUS_B",
        "tripId": "TRIP_B",
        "lat": 6.9280,
        "lon": 79.8620,
        "speed": 46.0,
        "timestamp": (base_time - timedelta(seconds=10)).isoformat(),
    }

    result_a = validator.validate(json.dumps(payload_a).encode("utf-8"))
    assert result_a.success is True

    result_b = validator.validate(json.dumps(payload_b).encode("utf-8"))
    assert result_b.success is True


def test_accepts_message_after_rate_window_and_updates_bus_state():
    validator = StatefulValidator()
    base_time = datetime.now(timezone.utc)

    payload1 = {
        "busId": "BUS_004",
        "tripId": "TRIP_004",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat(),
    }
    payload2 = {
        "busId": "BUS_004",
        "tripId": "TRIP_004",
        "lat": 6.9290,
        "lon": 79.8640,
        "speed": 47.0,
        "timestamp": (base_time + timedelta(seconds=5)).isoformat(),
    }

    first_result = validator.validate(json.dumps(payload1).encode("utf-8"))
    assert first_result.success is True

    second_result = validator.validate(json.dumps(payload2).encode("utf-8"))

    assert second_result.success is True
    bus_state = validator._bus_state["BUS_004"]
    assert bus_state.last_timestamp == second_result.message.timestamp
    assert bus_state.last_lat == second_result.message.lat
    assert bus_state.last_lon == second_result.message.lon
    assert len(bus_state.recent_hashes) == 2


def test_custom_stateful_validator_configuration_overrides_defaults():
    validator = StatefulValidator(
        duplicate_cache_size=5,
        min_event_interval_seconds=4.5,
    )

    assert validator._duplicate_cache_size == 5
    assert validator._min_event_interval_seconds == 4.5


def test_legacy_min_message_interval_configuration_maps_to_event_time():
    validator = StatefulValidator(min_message_interval_seconds=4.5)

    assert validator._min_event_interval_seconds == 4.5
    assert validator._min_message_interval_seconds == 4.5


def test_future_timestamp_rejected():
    validator = StatefulValidator()
    payload = {
        "busId": "BUS_FUTURE",
        "tripId": "TRIP_FUTURE",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }

    result = validator.validate(json.dumps(payload).encode("utf-8"))

    assert result.success is False
    assert result.error_type == "FUTURE_TIMESTAMP"


def test_stale_replay_rejected():
    validator = StatefulValidator()
    payload = {
        "busId": "BUS_STALE",
        "tripId": "TRIP_STALE",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    }

    result = validator.validate(json.dumps(payload).encode("utf-8"))

    assert result.success is False
    assert result.error_type == "STALE_REPLAY"


def test_same_timestamp_different_coordinates_is_event_time_rate_limited():
    validator = StatefulValidator()
    base_time = datetime.now(timezone.utc)
    payload1 = {
        "busId": "BUS_SAME_TS",
        "tripId": "TRIP_SAME_TS",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 45.5,
        "timestamp": base_time.isoformat(),
    }
    payload2 = {
        "busId": "BUS_SAME_TS",
        "tripId": "TRIP_SAME_TS",
        "lat": 6.9280,
        "lon": 79.8620,
        "speed": 45.5,
        "timestamp": base_time.isoformat(),
    }

    result1 = validator.validate(json.dumps(payload1).encode("utf-8"))
    assert result1.success is True

    result2 = validator.validate(json.dumps(payload2).encode("utf-8"))
    assert result2.success is False
    assert result2.error_type == "RATE_LIMIT_EVENT_TIME"
