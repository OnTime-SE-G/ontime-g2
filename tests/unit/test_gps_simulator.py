# tests/unit/test_gps_simulator.py

from scripts.gps_simulator import (
    haversine_km,
    create_message,
)


def test_haversine_zero_distance():
    distance = haversine_km(
        79.8612, 6.9271,
        79.8612, 6.9271
    )

    assert distance == 0


def test_haversine_positive_distance():
    distance = haversine_km(
        79.8612, 6.9271,
        79.8712, 6.9371
    )

    assert distance > 0


def test_create_message_has_required_fields():
    payload = create_message(
        79.8612, 6.9271,
        79.8712, 6.9371,
        4
    )

    expected_keys = {
        "busId",
        "routeId",
        "lat",
        "lng",
        "speed",
        "crowdStatus",
        "timestamp",
    }

    assert expected_keys == set(payload.keys())


def test_create_message_coordinates_precision():
    payload = create_message(
        79.86123456, 6.92712345,
        79.87129876, 6.93718765,
        4
    )

    assert payload["lat"] == round(payload["lat"], 6)
    assert payload["lng"] == round(payload["lng"], 6)


def test_create_message_speed_non_negative():
    payload = create_message(
        79.8612, 6.9271,
        79.8712, 6.9371,
        4
    )

    assert payload["speed"] >= 0


def test_create_message_valid_crowd_status():
    payload = create_message(
        79.8612, 6.9271,
        79.8712, 6.9371,
        4
    )

    assert payload["crowdStatus"] in {
        "NOT_FULL",
        "SEMI_FULL",
        "FULL",
    }


def test_create_message_timestamp_format():
    payload = create_message(
        79.8612, 6.9271,
        79.8712, 6.9371,
        4
    )

    assert "T" in payload["timestamp"]
    assert payload["timestamp"].endswith("Z")