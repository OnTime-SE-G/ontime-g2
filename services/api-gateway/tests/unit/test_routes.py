import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

API_GATEWAY_ROOT = Path(__file__).resolve().parents[2]
if str(API_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(API_GATEWAY_ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_routes():
    with patch("app.routers.routes.get_routes_list", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = [{"id": 1, "name": "Route 1", "route_number": "1", "color": "#fff", "destination": "Dest"}]
        response = client.get("/api/v1/routes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Route 1"

def test_search_for_routes():
    with patch("app.routers.routes.search_routes", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = {
            "count": 1, 
            "routes": [{"route_id": 1, "name": "Test", "start_stop_id": 1, "start_stop_name": "A", "end_stop_id": 2, "end_stop_name": "B"}]
        }
        response = client.get("/api/v1/routes/search?start_lat=1.0&start_lon=1.0&end_lat=2.0&end_lon=2.0")
        assert response.status_code == 200
        assert response.json()["count"] == 1

def test_get_transit_route():
    with patch("app.routers.routes.get_route", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"type": "FeatureCollection", "features": []}
        with patch("app.routers.routes.build_transit_route") as mock_build:
            mock_build.return_value = {"id": "1", "name": "Transit"}
            response = client.get("/api/v1/routes/1/transit-data")
            assert response.status_code == 200
            assert response.json() == {"id": "1", "name": "Transit"}

def test_get_all_transit_routes():
    with patch("app.routers.routes.get_routes_list", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [{"id": 1, "name": "R1"}]
        with patch("app.routers.routes.get_route", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"type": "FeatureCollection", "features": []}
            with patch("app.routers.routes.build_transit_route") as mock_build:
                mock_build.return_value = {"id": "1", "name": "Transit"}
                response = client.get("/api/v1/routes/all-transit-data")
                assert response.status_code == 200
                assert response.json() == {"1": {"id": "1", "name": "Transit"}}

def test_route_progress():
    with patch("app.routers.routes.get_route_progress", new_callable=AsyncMock) as mock_prog:
        mock_prog.return_value = {
            "route_id": 1, "target_stop_order": 2, "target_stop_name": "B",
            "travelled_m": 100.0, "remaining_m": 50.0, "total_to_target_m": 150.0, "progress_pct": 66.6
        }
        response = client.get("/api/v1/routes/1/progress?lat=1.0&lon=1.0&target_stop_order=2")
        assert response.status_code == 200
        assert response.json()["progress_pct"] == 66.6

def test_route_stops():
    with patch("app.routers.routes.get_route_stops", new_callable=AsyncMock) as mock_stops:
        mock_stops.return_value = {"route_id": 1, "route_name": "R1", "stops": []}
        response = client.get("/api/v1/routes/1/stops")
        assert response.status_code == 200
        assert response.json()["route_name"] == "R1"

def test_route_buses():
    with patch("app.routers.routes.get_route_buses", new_callable=AsyncMock) as mock_buses:
        mock_buses.return_value = {"route_id": 1, "buses": [], "message": "OK"}
        response = client.get("/api/v1/routes/1/buses")
        assert response.status_code == 200
        assert response.json()["message"] == "OK"
