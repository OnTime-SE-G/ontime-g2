from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_driver_get_today_trips():
    with patch("app.routers.driver.get_today_trips", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [{"id": "trip1", "schedule_id": 1, "status": "WAITING_AT_DEPOT", "date": "2026-05-03"}]
        response = client.get("/api/v1/driver/trips/today")
        assert response.status_code == 200
        assert response.json()[0]["id"] == "trip1"

def test_driver_start_trip():
    with patch("app.routers.driver.start_planned_trip", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"id": "trip1", "schedule_id": 1, "status": "EN_ROUTE", "date": "2026-05-03"}
        response = client.post("/api/v1/driver/trips/trip1/start")
        assert response.status_code == 200
        assert response.json()["status"] == "EN_ROUTE"

def test_driver_end_trip():
    with patch("app.routers.driver.end_planned_trip", new_callable=AsyncMock) as mock_end:
        mock_end.return_value = {"id": "trip1", "schedule_id": 1, "status": "ARRIVED_DESTINATION", "date": "2026-05-03"}
        response = client.post("/api/v1/driver/trips/trip1/end")
        assert response.status_code == 200
        assert response.json()["status"] == "ARRIVED_DESTINATION"

def test_driver_report_delay():
    with patch("app.routers.driver.report_trip_delay", new_callable=AsyncMock) as mock_delay:
        mock_delay.return_value = {"id": "trip1", "status": "EN_ROUTE", "delay_minutes": 10}
        response = client.post("/api/v1/driver/trips/trip1/report-delay", json={"delay_minutes": 10})
        assert response.status_code == 200
        assert response.json()["delay_minutes"] == 10

def test_driver_report_incident():
    with patch("app.routers.driver.report_trip_incident", new_callable=AsyncMock) as mock_incident:
        mock_incident.return_value = {"id": "trip1", "status": "INCIDENT_REPORTED", "last_incident_type": "BREAKDOWN"}
        response = client.post(
            "/api/v1/driver/trips/trip1/report-incident", 
            json={"incident_type": "BREAKDOWN", "message": "Engine issues"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "INCIDENT_REPORTED"
