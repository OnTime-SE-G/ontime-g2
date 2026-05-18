import pytest
from datetime import datetime, timezone

import app.models.anomaly_model as anomaly_model_module
from app.models.anomaly_model import AnomalyModel

@pytest.fixture
def model():
    return AnomalyModel()

def test_detect_unrealistic_speed(model):
    telemetry = {
        "busId": "B1",
        "tripId": "T1",
        "routeId": "R1",
        "lat": 6.9,
        "lon": 79.9,
        "speed": 150.0,
        "timestamp": "2026-05-02T10:00:00Z"
    }
    alerts = model.detect(telemetry, [])
    print(f"\n>>> DETECTED {len(alerts)} ALERTS: {alerts}")
    assert len(alerts) >= 1
    assert any(a["anomalyType"] == "UNREALISTIC_SPEED" for a in alerts)

def test_detect_inactive_gps(model):
    telemetry = {
        "busId": "B1",
        "tripId": "T1",
        "routeId": None,
        "lat": 6.9,
        "lon": 79.9,
        "speed": 20.0,
        "timestamp": "2026-05-02T10:00:00Z"
    }
    alerts = model.detect(telemetry, [])
    print(f"\n>>> DETECTED {len(alerts)} ALERTS: {alerts}")
    assert len(alerts) == 1
    assert alerts[0]["anomalyType"] == "INACTIVE_GPS"

def test_detect_inactive_trip_dlq_alerts_after_threshold(model):
    envelope = {
        "busId": "1",
        "error_type": "INACTIVE_TRIP",
        "error_reason": "No active trip found for bus 1",
        "original_payload": (
            '{"busId":"1","lat":6.9271,"lon":79.8612,'
            '"speed":20.0,"timestamp":"2026-05-02T10:00:00Z"}'
        ),
        "received_at": "2026-05-02T10:00:00Z",
    }

    first = model.detect_inactive_trip_dlq(
        envelope,
        now=datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc),
        threshold_count=3,
        window_seconds=60,
    )
    second = model.detect_inactive_trip_dlq(
        envelope,
        now=datetime(2026, 5, 2, 10, 0, 20, tzinfo=timezone.utc),
        threshold_count=3,
        window_seconds=60,
    )
    third = model.detect_inactive_trip_dlq(
        envelope,
        now=datetime(2026, 5, 2, 10, 0, 40, tzinfo=timezone.utc),
        threshold_count=3,
        window_seconds=60,
    )

    assert first == []
    assert second == []
    assert len(third) == 1
    alert = third[0]
    assert alert["anomalyType"] == "TRIP_NOT_STARTED_DEVICE_ACTIVE"
    assert alert["busId"] == "1"
    assert alert["source"] == "transport-telemetry-dlq"
    assert alert["sourceReason"] == "INACTIVE_TRIP"
    assert alert["dlqCount"] == 3
    assert alert["location"] == {"lat": 6.9271, "lon": 79.8612}


def test_detect_inactive_trip_dlq_uses_cooldown(model):
    envelope = {
        "busId": "1",
        "error_type": "INACTIVE_TRIP",
        "original_payload": '{"busId":"1","lat":6.9,"lon":79.9}',
    }

    first_alerts = []
    for second in (0, 10, 20):
        first_alerts = model.detect_inactive_trip_dlq(
            envelope,
            now=datetime(2026, 5, 2, 10, 0, second, tzinfo=timezone.utc),
            threshold_count=3,
            window_seconds=60,
            cooldown_seconds=300,
        )

    duplicate_alerts = model.detect_inactive_trip_dlq(
        envelope,
        now=datetime(2026, 5, 2, 10, 1, 0, tzinfo=timezone.utc),
        threshold_count=3,
        window_seconds=60,
        cooldown_seconds=300,
    )

    assert len(first_alerts) == 1
    assert duplicate_alerts == []


def test_detect_inactive_trip_dlq_ignores_other_dlq_reasons(model):
    envelope = {
        "busId": "1",
        "error_type": "INVALID_JSON",
        "error_reason": "Failed to parse JSON",
    }

    alerts = model.detect_inactive_trip_dlq(
        envelope,
        now=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
        threshold_count=1,
    )

    assert alerts == []


def test_detect_inactive_trip_dlq_can_extract_bus_id_from_original_payload(model):
    envelope = {
        "error_type": "INACTIVE_TRIP",
        "original_payload": '{"busId":"42","lat":6.9,"lon":79.9}',
    }

    alerts = model.detect_inactive_trip_dlq(
        envelope,
        now=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
        threshold_count=1,
    )

    assert len(alerts) == 1
    assert alerts[0]["busId"] == "42"

def test_detect_off_route(model):
    # Colpetty coordinates (6.91, 79.85)
    # Route geometry at Bambalapitiya (6.89, 79.85)
    route_geom = [(6.89, 79.85), (6.895, 79.85)]
    telemetry = {
        "busId": "B1",
        "tripId": "T1",
        "routeId": "R1",
        "lat": 6.91,
        "lon": 79.85,
        "speed": 20.0,
        "timestamp": "2026-05-02T10:00:00Z"
    }
    # Distance between 6.91 and 6.895 is ~1.6km, which is > 50m
    alerts = model.detect(telemetry, route_geom)
    print(f"\n>>> DETECTED {len(alerts)} ALERTS: {alerts}")
    assert any(a["anomalyType"] == "OFF_ROUTE" for a in alerts)


def test_detect_off_route_uses_flink_flag_without_geometry(model):
    telemetry = {
        "busId": "B1",
        "tripId": "T1",
        "routeId": "R1",
        "lat": 6.91,
        "lon": 79.85,
        "speed": 20.0,
        "timestamp": "2026-05-02T10:00:00Z",
        "offRoute": True,
        "offRouteDistanceM": 83.4,
    }

    alerts = model.detect(telemetry, [])

    assert any(a["anomalyType"] == "OFF_ROUTE" for a in alerts)


def test_detect_persistent_off_route_after_streak(model):
    base = {
        "busId": "B1",
        "tripId": "T1",
        "routeId": "R1",
        "lat": 6.91,
        "lon": 79.85,
        "speed": 20.0,
        "offRoute": True,
        "offRouteDistanceM": 83.4,
    }

    first = model.detect({**base, "timestamp": "2026-05-02T10:00:00Z"}, [])
    second = model.detect({**base, "timestamp": "2026-05-02T10:00:01Z"}, [])
    third = model.detect({**base, "timestamp": "2026-05-02T10:00:02Z"}, [])

    assert not any(a["anomalyType"] == "PERSISTENT_OFF_ROUTE" for a in first)
    assert not any(a["anomalyType"] == "PERSISTENT_OFF_ROUTE" for a in second)
    persistent = [a for a in third if a["anomalyType"] == "PERSISTENT_OFF_ROUTE"]
    assert len(persistent) == 1
    assert persistent[0]["streakCount"] == 3

def test_detect_stationary_bus(model):
    from datetime import datetime, timedelta, timezone
    bus_id = "B1"
    route_geom = [(6.9, 79.9), (6.91, 79.91)]
    start_time = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(12):
        ts = (start_time + timedelta(seconds=i*30)).isoformat().replace("+00:00", "Z")
        telemetry = {
            "busId": bus_id, "tripId": "T1", "routeId": "R1",
            "lat": 6.9 + (i * 0.00001), # Small jitter
            "lon": 79.9 + (i * 0.00001),
            "speed": 1.0,
            "timestamp": ts
        }
        alerts = model.detect(telemetry, route_geom)
        if i < 10:
            assert not any(a["anomalyType"] == "STATIONARY" for a in alerts)
        elif i == 10:
            assert any(a["anomalyType"] == "STATIONARY" for a in alerts)
        else:
            # Already alerted, so shouldn't alert again
            assert not any(a["anomalyType"] == "STATIONARY" for a in alerts)

def test_detect_communication_loss(model):
    bus_id = "B1"

    telemetry1 = {
        "busId": bus_id, "tripId": "T1", "routeId": "R1",
        "lat": 6.9, "lon": 79.9, "speed": 20.0,
        "timestamp": "2026-05-02T10:00:00Z"
    }
    model.detect(telemetry1, [])

    alerts = model.detect_communication_loss(
        now=datetime(2026, 5, 2, 10, 4, tzinfo=timezone.utc),
        threshold_seconds=180,
    )
    print(f"\n>>> DETECTED {len(alerts)} ALERTS: {alerts}")
    assert any(a["anomalyType"] == "COMMUNICATION_LOSS" for a in alerts)


def test_detect_communication_loss_only_alerts_once_until_new_telemetry(model):
    bus_id = "B1"
    telemetry1 = {
        "busId": bus_id, "tripId": "T1", "routeId": "R1",
        "lat": 6.9, "lon": 79.9, "speed": 20.0,
        "timestamp": "2026-05-02T10:00:00Z"
    }
    model.detect(telemetry1, [])

    first_alerts = model.detect_communication_loss(
        now=datetime(2026, 5, 2, 10, 4, tzinfo=timezone.utc),
        threshold_seconds=180,
    )
    duplicate_alerts = model.detect_communication_loss(
        now=datetime(2026, 5, 2, 10, 5, tzinfo=timezone.utc),
        threshold_seconds=180,
    )

    telemetry2 = {
        "busId": bus_id, "tripId": "T1", "routeId": "R1",
        "lat": 6.9, "lon": 79.9, "speed": 20.0,
        "timestamp": "2026-05-02T10:06:00Z"
    }
    model.detect(telemetry2, [])
    reset_alerts = model.detect_communication_loss(
        now=datetime(2026, 5, 2, 10, 10, tzinfo=timezone.utc),
        threshold_seconds=180,
    )

    assert len(first_alerts) == 1
    assert duplicate_alerts == []
    assert len(reset_alerts) == 1

def test_off_route_accuracy(model):
    """
    Test that the bus is NOT flagged as off-route if it's on the segment
    between vertices, even if it's far from the vertices themselves.
    """
    # Route: Straight line from (6.0, 80.0) to (6.1, 80.0) (~11km long)
    route_geom = [(6.0, 80.0), (6.1, 80.0)]

    # Bus is at (6.05, 80.0001) -> ~5.5km from either vertex, but only ~11m from the road
    telemetry = {
        "busId": "B1", "tripId": "T1", "routeId": "R1",
        "lat": 6.05, "lon": 80.0001, "speed": 40.0,
        "timestamp": "2026-05-02T10:00:00Z"
    }

    alerts = model.detect(telemetry, route_geom)
    print(f"\n>>> DETECTED {len(alerts)} ALERTS (Expected 0 OFF_ROUTE): {alerts}")

    # Accuracy Check:
    # Old logic would see distance to (6.0, 80.0) as 5500m -> OFF_ROUTE!
    # New logic sees distance to road as 11m -> OK!
    assert not any(a["anomalyType"] == "OFF_ROUTE" for a in alerts)


def test_behavioral_detection_waits_for_minimum_window(monkeypatch):
    monkeypatch.setattr(anomaly_model_module.settings, "sliding_window_size", 4)
    monkeypatch.setattr(anomaly_model_module.settings, "sliding_window_min_size", 3)

    model = AnomalyModel()

    class FakeIsolationModel:
        def __init__(self):
            self.calls = []

        def predict(self, rows):
            self.calls.append(rows[0])
            return [-1]

    fake_model = FakeIsolationModel()
    model.isolation_model = fake_model

    base = {
        "busId": "B1",
        "tripId": "T1",
        "routeId": "R1",
        "lat": 6.9,
        "lon": 79.9,
        "heading": 10.0,
    }

    first = model.detect({**base, "speed": 10.0, "timestamp": "2026-05-02T10:00:00Z"}, [])
    second = model.detect({**base, "speed": 12.0, "timestamp": "2026-05-02T10:00:01Z"}, [])
    third = model.detect({**base, "speed": 30.0, "timestamp": "2026-05-02T10:00:02Z"}, [])

    assert not any(a["anomalyType"] == "ERRATIC_DRIVING" for a in first)
    assert not any(a["anomalyType"] == "ERRATIC_DRIVING" for a in second)
    assert any(a["anomalyType"] == "ERRATIC_DRIVING" for a in third)
    assert len(fake_model.calls) == 1
    assert len(fake_model.calls[0]) == 6


def test_behavioral_detection_keeps_sliding_window_bounded(monkeypatch):
    monkeypatch.setattr(anomaly_model_module.settings, "sliding_window_size", 3)
    monkeypatch.setattr(anomaly_model_module.settings, "sliding_window_min_size", 2)

    model = AnomalyModel()

    class NormalIsolationModel:
        def predict(self, rows):
            return [1]

    model.isolation_model = NormalIsolationModel()

    base = {
        "busId": "B2",
        "tripId": "T1",
        "routeId": "R1",
        "lat": 6.9,
        "lon": 79.9,
        "heading": 10.0,
    }

    for index in range(6):
        model.detect(
            {
                **base,
                "speed": 10.0 + index,
                "timestamp": f"2026-05-02T10:00:0{index}Z",
            },
            [],
        )

    assert len(model.telemetry_windows["B2"]) == 3
    assert model.telemetry_windows["B2"][0]["timestamp"] == "2026-05-02T10:00:03Z"


def test_behavioral_rules_fallback_when_isolation_forest_missing(monkeypatch):
    monkeypatch.setattr(anomaly_model_module.settings, "sliding_window_size", 3)
    monkeypatch.setattr(anomaly_model_module.settings, "sliding_window_min_size", 2)
    monkeypatch.setattr(anomaly_model_module.settings, "behavioral_fallback_speed_variance", 8.0)
    monkeypatch.setattr(anomaly_model_module.settings, "behavioral_fallback_heading_variance", 5.0)
    monkeypatch.setattr(anomaly_model_module.settings, "behavioral_fallback_max_acceleration", 3.0)

    model = AnomalyModel()
    model.isolation_model = None

    base = {
        "busId": "B3",
        "tripId": "T1",
        "routeId": "R1",
        "lat": 6.9,
        "lon": 79.9,
        "heading": 10.0,
    }
    speeds = [10.0, 45.0, 5.0, 50.0]
    alerts = []
    for index, speed in enumerate(speeds):
        alerts = model.detect(
            {**base, "speed": speed, "timestamp": f"2026-05-02T10:00:0{index}Z"},
            [],
        )

    erratic = [a for a in alerts if a["anomalyType"] == "ERRATIC_DRIVING"]
    assert erratic
    assert erratic[-1]["detectionMethod"] == "rules_fallback"


def test_canonical_isolation_forest_artifact_loads():
    from pathlib import Path

    artifact = Path(__file__).resolve().parents[2] / "app" / "models" / "training" / "isolation_forest.joblib"
    assert artifact.exists(), "Commit isolation_forest.joblib with the service"

    model = AnomalyModel()
    assert model.isolation_model is not None
    assert model.isolation_model_version is not None
