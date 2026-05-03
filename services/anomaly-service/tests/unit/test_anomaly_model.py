import pytest
from datetime import datetime, timezone

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

def test_detect_stationary_bus(model):
    bus_id = "B1"
    route_geom = [(6.9, 79.9), (6.91, 79.91)]

    # 1. First message: stationary
    telemetry1 = {
        "busId": bus_id, "tripId": "T1", "routeId": "R1",
        "lat": 6.9, "lon": 79.9, "speed": 1.0,
        "timestamp": "2026-05-02T10:00:00Z"
    }
    alerts = model.detect(telemetry1, route_geom)
    assert not any(a["anomalyType"] == "STATIONARY" for a in alerts)

    # 2. Second message: 6 minutes later, still stationary
    telemetry2 = {
        "busId": bus_id, "tripId": "T1", "routeId": "R1",
        "lat": 6.9, "lon": 79.9, "speed": 1.0,
        "timestamp": "2026-05-02T10:06:00Z"
    }
    alerts = model.detect(telemetry2, route_geom)
    print(f"\n>>> DETECTED {len(alerts)} ALERTS: {alerts}")
    assert any(a["anomalyType"] == "STATIONARY" for a in alerts)

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
