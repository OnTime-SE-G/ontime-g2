import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

API_GATEWAY_ROOT = Path(__file__).resolve().parents[2]
if str(API_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(API_GATEWAY_ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_bus():
    with patch("app.routers.admin_fleet.add_bus", new_callable=AsyncMock) as mock_add:
        mock_add.return_value = {"id": "bus1", "status": "idle", "route_id": None, "capacity": 50}
        response = client.post("/api/v1/admin/fleet/buses", json={"id": "bus1", "capacity": 50})
        assert response.status_code == 200
        assert response.json()["id"] == "bus1"

def test_modify_bus():
    with patch("app.routers.admin_fleet.update_bus", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = {"id": "bus1", "status": "maintenance", "route_id": None, "capacity": 50}
        response = client.put("/api/v1/admin/fleet/buses/bus1", json={"status": "maintenance"})
        assert response.status_code == 200
        assert response.json()["status"] == "maintenance"

def test_remove_bus():
    with patch("app.routers.admin_fleet.delete_bus", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = {"message": "Deleted", "bus_id": "bus1"}
        response = client.delete("/api/v1/admin/fleet/buses/bus1")
        assert response.status_code == 200
        assert response.json()["message"] == "Deleted"

def test_assign_bus_to_route():
    with patch("app.routers.admin_fleet.assign_route", new_callable=AsyncMock) as mock_assign:
        mock_assign.return_value = {"message": "Assigned", "bus_id": "bus1", "route_id": "r1"}
        response = client.post("/api/v1/admin/fleet/buses/bus1/assign-route/r1")
        assert response.status_code == 200
        assert response.json()["route_id"] == "r1"

def test_unassign_bus():
    with patch("app.routers.admin_fleet.unassign_route", new_callable=AsyncMock) as mock_unassign:
        mock_unassign.return_value = {"message": "Unassigned", "bus_id": "bus1", "route_id": None}
        response = client.post("/api/v1/admin/fleet/buses/bus1/unassign")
        assert response.status_code == 200
        assert response.json()["message"] == "Unassigned"
