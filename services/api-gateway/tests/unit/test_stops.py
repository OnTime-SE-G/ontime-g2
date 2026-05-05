import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

API_GATEWAY_ROOT = Path(__file__).resolve().parents[2]
if str(API_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(API_GATEWAY_ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_all_stops():
    with patch("app.routers.stops.get_all_stops", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [{"id": 1, "name": "Stop 1", "coordinates": [1.0, 1.0], "routes": []}]
        response = client.get("/api/v1/stops")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Stop 1"

def test_nearby_stops():
    with patch("app.routers.stops.get_nearby_stops", new_callable=AsyncMock) as mock_nearby:
        mock_nearby.return_value = [{"id": 1, "name": "Stop 1", "distance_m": 50.0, "routes": []}]
        response = client.get("/api/v1/stops/nearby?lat=1.0&lon=1.0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["distance_m"] == 50.0

def test_routes_for_stop():
    with patch("app.routers.stops.get_routes_for_stop", new_callable=AsyncMock) as mock_routes:
        mock_routes.return_value = [{"id": 1, "name": "Route 1", "route_number": "R1"}]
        response = client.get("/api/v1/stops/1/routes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["route_number"] == "R1"
