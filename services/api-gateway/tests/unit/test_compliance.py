from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_trip_state():
    with patch("app.routers.trips.get_trip_detail", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {
            "id": "trip1",
            "schedule_id": 1,
            "status": "EN_ROUTE",
            "date": "2026-05-03",
            "delay_minutes": 5,
            "actual_start_time": "2026-05-03T10:00:00Z"
        }
        # Testing the specific endpoint requested in the project plan
        response = client.get("/api/v1/trips/trip1/state")
        # If this fails with 404, it confirms the endpoint is missing from the router
        assert response.status_code == 200
        assert response.json()["id"] == "trip1"


