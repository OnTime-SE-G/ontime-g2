# tests/unit/test_trips.py
# Tests for Driver, Schedule, PlannedTrip lifecycle endpoints.
# Kafka publishing is mocked — these tests focus on DB state transitions.

from datetime import date, time
from unittest.mock import AsyncMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_bus(client, fleet_code="BUS-001", plate="NB-1234"):
    r = client.post(
        "/api/v1/fleet/buses",
        json={"fleet_code": fleet_code, "plate_number": plate, "capacity": 40},
    )
    assert r.status_code == 200
    return r.json()


def _create_driver(client, name="Alice", license_no="D-001"):
    r = client.post(
        "/api/v1/fleet/drivers",
        json={"name": name, "license_number": license_no, "phone": "0771234567"},
    )
    assert r.status_code == 200
    return r.json()


def _create_schedule(client, route_id=1):
    with patch(
        "app.services.route_service.validate_route_exists", return_value=None
    ):
        r = client.post(
            "/api/v1/fleet/schedules",
            json={
                "route_id": route_id,
                "scheduled_time": "08:30:00",
                "day_of_week": date.today().weekday(),
            },
        )
    assert r.status_code == 200
    return r.json()


# ── Driver Tests ──────────────────────────────────────────────────────────────

def test_create_driver(client):
    driver = _create_driver(client)
    assert driver["name"] == "Alice"
    assert driver["license_number"] == "D-001"
    assert driver["id"] is not None


def test_get_drivers_empty(client):
    r = client.get("/api/v1/fleet/drivers")
    assert r.status_code == 200
    assert r.json() == []


def test_get_drivers_returns_created(client):
    _create_driver(client)
    r = client.get("/api/v1/fleet/drivers")
    assert r.status_code == 200
    assert len(r.json()) == 1


# ── Schedule Tests ─────────────────────────────────────────────────────────────

def test_create_schedule(client):
    schedule = _create_schedule(client, route_id=1)
    assert schedule["route_id"] == 1
    assert schedule["scheduled_time"] == "08:30:00"
    assert schedule["id"] is not None


def test_create_schedule_validates_route(client):
    """Should return 503/404 when route service says route does not exist."""
    with patch(
        "app.services.route_service.validate_route_exists",
        side_effect=Exception("route not found"),
    ):
        r = client.post(
            "/api/v1/fleet/schedules",
            json={"route_id": 9999, "scheduled_time": "09:00:00", "day_of_week": 0},
        )
    assert r.status_code >= 400


# ── Planned Trip Generation Tests ─────────────────────────────────────────────

def test_generate_trips_creates_records(client):
    _create_schedule(client)
    today = date.today().isoformat()

    r = client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1


def test_generate_trips_is_idempotent(client):
    """Calling generate twice on the same date should not create duplicates."""
    _create_schedule(client)
    today = date.today().isoformat()

    client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")
    r = client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")
    assert r.status_code == 200
    assert r.json()["count"] == 0  # No new trips created


def test_get_today_trips(client):
    _create_schedule(client)
    today = date.today().isoformat()
    client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")

    r = client.get("/api/v1/fleet/planned-trips/today")
    assert r.status_code == 200
    trips = r.json()
    assert len(trips) == 1
    assert trips[0]["status"] == "WAITING_AT_DEPOT"


# ── Trip Lifecycle Tests ───────────────────────────────────────────────────────

@patch("app.services.trip_service.kafka_service")
def test_start_trip_transitions_to_en_route(mock_kafka, client):
    mock_kafka.publish_trip_event = AsyncMock()

    bus = _create_bus(client)
    driver = _create_driver(client)
    _create_schedule(client)

    today = date.today().isoformat()
    client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")
    trips = client.get("/api/v1/fleet/planned-trips/today").json()
    trip_id = trips[0]["id"]

    # Assign bus and driver
    client.patch(f"/api/v1/fleet/planned-trips/{trip_id}/assign?bus_id={bus['id']}&driver_id={driver['id']}")

    # Start the trip
    r = client.post(f"/api/v1/fleet/planned-trips/{trip_id}/start")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "EN_ROUTE"
    assert data["actual_start_time"] is not None

    # Kafka event should have been published
    mock_kafka.publish_trip_event.assert_called_once()


@patch("app.services.trip_service.kafka_service")
def test_end_trip_transitions_to_arrived(mock_kafka, client):
    mock_kafka.publish_trip_event = AsyncMock()

    bus = _create_bus(client)
    driver = _create_driver(client)
    _create_schedule(client)

    today = date.today().isoformat()
    client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")
    trips = client.get("/api/v1/fleet/planned-trips/today").json()
    trip_id = trips[0]["id"]

    client.patch(f"/api/v1/fleet/planned-trips/{trip_id}/assign?bus_id={bus['id']}&driver_id={driver['id']}")
    client.post(f"/api/v1/fleet/planned-trips/{trip_id}/start")

    # End the trip
    r = client.post(f"/api/v1/fleet/planned-trips/{trip_id}/end")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ARRIVED_DESTINATION"
    assert data["actual_end_time"] is not None

    # Both TRIP_STARTED and TRIP_ENDED events published
    assert mock_kafka.publish_trip_event.call_count == 2


def test_report_delay(client):
    _create_schedule(client)
    today = date.today().isoformat()
    client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")
    trips = client.get("/api/v1/fleet/planned-trips/today").json()
    trip_id = trips[0]["id"]

    # Report 15 min delay
    r = client.post(f"/api/v1/fleet/planned-trips/{trip_id}/delay", json={"delay_minutes": 15})
    assert r.status_code == 200
    assert r.json()["delay_minutes"] == 15


@patch("app.services.trip_service.kafka_service")
def test_report_incident(mock_kafka, client):
    mock_kafka.publish_trip_event = AsyncMock()
    
    bus = _create_bus(client)
    driver = _create_driver(client)
    _create_schedule(client)
    today = date.today().isoformat()
    client.post(f"/api/v1/fleet/planned-trips/generate?target_date={today}")
    trips = client.get("/api/v1/fleet/planned-trips/today").json()
    trip_id = trips[0]["id"]
    client.patch(f"/api/v1/fleet/planned-trips/{trip_id}/assign?bus_id={bus['id']}&driver_id={driver['id']}")
    client.post(f"/api/v1/fleet/planned-trips/{trip_id}/start")

    # Report breakdown
    r = client.post(
        f"/api/v1/fleet/planned-trips/{trip_id}/incident", 
        json={"incident_type": "BREAKDOWN", "message": "Engine overheating"}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "INCIDENT_REPORTED"
    assert data["last_incident_type"] == "BREAKDOWN"
    
    # Kafka INCIDENT_REPORTED event should be published
    mock_kafka.publish_trip_event.assert_called()
