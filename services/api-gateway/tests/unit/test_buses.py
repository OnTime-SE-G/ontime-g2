from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_live_buses():
    with patch("app.routers.buses.get_buses", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [{"id": "bus1", "status": "active", "route_id": "r1", "capacity": 50}]
        response = client.get("/api/v1/buses/live")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "bus1"
        assert "latitude" in data[0]

def test_fetch_bus():
    with patch("app.routers.buses.get_bus", new_callable=AsyncMock) as mock_bus:
        mock_bus.return_value = {"id": "bus1", "status": "active", "route_id": "r1", "capacity": 50}
        response = client.get("/api/v1/buses/bus1")
        assert response.status_code == 200
        assert response.json()["id"] == "bus1"

def test_fetch_buses_by_route():
    with patch("app.routers.buses.get_route_buses", new_callable=AsyncMock) as mock_buses:
        mock_buses.return_value = [{"id": "bus1", "status": "active", "route_id": "r1", "capacity": 50}]
        response = client.get("/api/v1/buses/route/r1")
        assert response.status_code == 200
        assert len(response.json()) == 1
