import base64
import json
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TRIP_FIXTURE = {
    "id": "trip1",
    "schedule_id": 1,
    "bus_id": 1,
    "driver_id": 4,
    "date": "2026-05-10",
    "status": "WAITING_AT_DEPOT",
    "actual_start_time": None,
    "actual_end_time": None,
    "delay_minutes": 0,
    "last_incident_type": None,
}

DRIVER_FIXTURE = {
    "id": 4,
    "name": "Kusal Pabasara",
    "license_number": "DL-001",
    "phone": "0771234567",
    "auth_user_id": "kc-sub-abc123",
    "username": "kusal.p",
    "is_active": True,
}


def _make_jwt(sub: str) -> str:
    """Build a minimal fake JWT with the given sub claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": sub, "exp": 9999999999}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def test_driver_get_me():
    with patch("app.routers.driver.get_driver_by_auth_id", new_callable=AsyncMock) as mock:
        mock.return_value = DRIVER_FIXTURE
        token = _make_jwt("kc-sub-abc123")
        response = client.get("/api/v1/driver/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["auth_user_id"] == "kc-sub-abc123"
        mock.assert_called_once_with("kc-sub-abc123")


def test_driver_get_me_missing_token():
    response = client.get("/api/v1/driver/me")
    assert response.status_code == 401


def test_driver_get_today_trips():
    with patch("app.routers.driver.get_today_trips", new_callable=AsyncMock) as mock:
        mock.return_value = [TRIP_FIXTURE]
        response = client.get("/api/v1/driver/trips/today")
        assert response.status_code == 200
        assert len(response.json()) == 1
        mock.assert_called_once_with(driver_id=None)


def test_driver_get_today_trips_filtered():
    with patch("app.routers.driver.get_today_trips", new_callable=AsyncMock) as mock:
        mock.return_value = [TRIP_FIXTURE]
        response = client.get("/api/v1/driver/trips/today?driver_id=4")
        assert response.status_code == 200
        mock.assert_called_once_with(driver_id=4)


def test_driver_get_trip_detail():
    with patch("app.routers.driver.get_trip_detail", new_callable=AsyncMock) as mock:
        mock.return_value = TRIP_FIXTURE
        response = client.get("/api/v1/driver/trips/trip1")
        assert response.status_code == 200
        assert response.json()["id"] == "trip1"


def test_driver_start_trip():
    with patch("app.routers.driver.start_planned_trip", new_callable=AsyncMock) as mock:
        mock.return_value = {**TRIP_FIXTURE, "status": "EN_ROUTE"}
        response = client.post("/api/v1/driver/trips/trip1/start")
        assert response.status_code == 200
        assert response.json()["status"] == "EN_ROUTE"


def test_driver_end_trip():
    with patch("app.routers.driver.end_planned_trip", new_callable=AsyncMock) as mock:
        mock.return_value = {**TRIP_FIXTURE, "status": "ARRIVED_DESTINATION"}
        response = client.post("/api/v1/driver/trips/trip1/end")
        assert response.status_code == 200
        assert response.json()["status"] == "ARRIVED_DESTINATION"


def test_driver_report_delay():
    with patch("app.routers.driver.report_trip_delay", new_callable=AsyncMock) as mock:
        mock.return_value = {**TRIP_FIXTURE, "delay_minutes": 10}
        response = client.post("/api/v1/driver/trips/trip1/report-delay", json={"delay_minutes": 10})
        assert response.status_code == 200
        assert response.json()["delay_minutes"] == 10
import base64
import json
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

TRIP_FIXTURE = {
    "id": "trip1",
    "schedule_id": 1,
    "bus_id": 1,
    "driver_id": 4,
    "date": "2026-05-10",
    "status": "WAITING_AT_DEPOT",
    "actual_start_time": None,
    "actual_end_time": None,
    "delay_minutes": 0,
    "last_incident_type": None,
}

DRIVER_FIXTURE = {
    "id": 4,
    "name": "Kusal Pabasara",
    "license_number": "DL-001",
    "phone": "0771234567",
    "auth_user_id": "kc-sub-abc123",
    "username": "kusal.p",
    "is_active": True,
}


def _make_jwt(sub: str) -> str:
    """Build a minimal fake JWT with the given sub claim."""
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": sub, "exp": 9999999999}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def test_driver_get_me():
    with patch("app.routers.driver.get_driver_by_auth_id", new_callable=AsyncMock) as mock:
        mock.return_value = DRIVER_FIXTURE
        token = _make_jwt("kc-sub-abc123")
        response = client.get("/api/v1/driver/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["auth_user_id"] == "kc-sub-abc123"
        mock.assert_called_once_with("kc-sub-abc123")


def test_driver_get_me_missing_token():
    response = client.get("/api/v1/driver/me")
    assert response.status_code == 401


def test_driver_get_today_trips():
    with patch("app.routers.driver.get_today_trips", new_callable=AsyncMock) as mock:
        mock.return_value = [TRIP_FIXTURE]
        response = client.get("/api/v1/driver/trips/today")
        assert response.status_code == 200
        assert len(response.json()) == 1
        mock.assert_called_once_with(driver_id=None)


def test_driver_get_today_trips_filtered():
    with patch("app.routers.driver.get_today_trips", new_callable=AsyncMock) as mock:
        mock.return_value = [TRIP_FIXTURE]
        response = client.get("/api/v1/driver/trips/today?driver_id=4")
        assert response.status_code == 200
        mock.assert_called_once_with(driver_id=4)


def test_driver_get_trip_detail():
    with patch("app.routers.driver.get_trip_detail", new_callable=AsyncMock) as mock:
        mock.return_value = TRIP_FIXTURE
        response = client.get("/api/v1/driver/trips/trip1")
        assert response.status_code == 200
        assert response.json()["id"] == "trip1"


def test_driver_start_trip():
    with patch("app.routers.driver.start_planned_trip", new_callable=AsyncMock) as mock:
        mock.return_value = {**TRIP_FIXTURE, "status": "EN_ROUTE"}
        response = client.post("/api/v1/driver/trips/trip1/start")
        assert response.status_code == 200
        assert response.json()["status"] == "EN_ROUTE"


def test_driver_end_trip():
    with patch("app.routers.driver.end_planned_trip", new_callable=AsyncMock) as mock:
        mock.return_value = {**TRIP_FIXTURE, "status": "ARRIVED_DESTINATION"}
        response = client.post("/api/v1/driver/trips/trip1/end")
        assert response.status_code == 200
        assert response.json()["status"] == "ARRIVED_DESTINATION"


def test_driver_report_delay():
    with patch("app.routers.driver.report_trip_delay", new_callable=AsyncMock) as mock:
        mock.return_value = {**TRIP_FIXTURE, "delay_minutes": 10}
        response = client.post("/api/v1/driver/trips/trip1/report-delay", json={"delay_minutes": 10})
        assert response.status_code == 200
        assert response.json()["delay_minutes"] == 10


def test_driver_report_incident():
    with patch("app.routers.driver.report_trip_incident", new_callable=AsyncMock) as mock:
        mock.return_value = {**TRIP_FIXTURE, "status": "INCIDENT_REPORTED"}
        response = client.post("/api/v1/driver/trips/trip1/report-incident", json={"incident_type": "BREAKDOWN"})
        assert response.status_code == 200
        assert response.json()["status"] == "INCIDENT_REPORTED"
