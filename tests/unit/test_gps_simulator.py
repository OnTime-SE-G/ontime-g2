# tests/unit/test_gps_simulator.py

import scripts.gps_simulator as gps_simulator
from scripts.gps_simulator import create_message, haversine_km


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


def test_publish_loop_sends_telemetry_to_configured_topic(monkeypatch):
    sent_messages = []
    flush_called = False
    close_called = False

    class FakeProducer:
        def send(self, topic, payload):
            sent_messages.append((topic, payload))

        def flush(self):
            nonlocal flush_called
            flush_called = True

        def close(self):
            nonlocal close_called
            close_called = True

    def fake_sleep(_seconds):
        gps_simulator.running = False

    monkeypatch.setattr(gps_simulator, "running", True)
    monkeypatch.setattr(gps_simulator, "get_producer", lambda: FakeProducer())
    monkeypatch.setattr(
        gps_simulator,
        "load_route_points",
        lambda: [
            (79.8612, 6.9271),
            (79.8712, 6.9371),
        ],
    )
    monkeypatch.setattr(gps_simulator.random, "randint", lambda _min, _max: 4)
    monkeypatch.setattr(gps_simulator.time, "sleep", fake_sleep)
    monkeypatch.setattr(gps_simulator.settings, "telemetry_topic", "transport-telemetry-raw")

    gps_simulator.publish_loop()

    assert len(sent_messages) == 1
    topic, payload = sent_messages[0]
    assert topic == gps_simulator.settings.telemetry_topic
    assert payload["routeId"] == gps_simulator.settings.route_name
    assert payload["busId"] == gps_simulator.settings.bus_id
    assert flush_called is True
    assert close_called is True
