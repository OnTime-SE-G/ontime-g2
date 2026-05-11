from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ── Bus Management ────────────────────────────────────────────────────────────

def test_create_bus():
    with patch("app.routers.admin_fleet.add_bus", new_callable=AsyncMock) as mock_add:
        mock_add.return_value = {"id": "1", "fleet_code": "B1", "plate_number": "P1", "capacity": 50, "route_id": None, "status": "active"}
        response = client.post("/api/v1/admin/fleet/buses", json={"fleet_code": "B1", "plate_number": "P1", "capacity": 50})
        assert response.status_code == 200
        assert response.json()["fleet_code"] == "B1"

def test_list_buses():
    with patch("app.routers.admin_fleet.get_buses", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [{"id": "1", "fleet_code": "B1", "plate_number": "P1", "capacity": 50, "route_id": None, "status": "active"}]
        response = client.get("/api/v1/admin/fleet/buses")
        assert response.status_code == 200
        assert len(response.json()) == 1

# ── Driver Management ─────────────────────────────────────────────────────────

def test_add_driver():
    with patch("app.routers.admin_fleet.keycloak_client.create_user") as mock_kc, \
         patch("app.routers.admin_fleet.create_driver", new_callable=AsyncMock) as mock_fleet:
        
        mock_kc.return_value = "kc-user-123"
        mock_fleet.return_value = {
            "id": 1, 
            "name": "Alice", 
            "license_number": "L1", 
            "phone": "123", 
            "username": "alice123", 
            "auth_user_id": "kc-user-123",
            "is_active": True
        }
        
        payload = {
            "name": "Alice", 
            "license_number": "L1", 
            "username": "alice123", 
            "password": "password123"
        }
        response = client.post("/api/v1/admin/fleet/drivers", json=payload)
        
        assert response.status_code == 200
        assert response.json()["name"] == "Alice"
        assert response.json()["auth_user_id"] == "kc-user-123"

def test_list_drivers():
    with patch("app.routers.admin_fleet.list_drivers", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [{"id": 1, "name": "Alice", "license_number": "L1", "phone": "123"}]
        response = client.get("/api/v1/admin/fleet/drivers")
        assert response.status_code == 200
        assert len(response.json()) == 1

def test_get_driver():
    with patch("app.routers.admin_fleet.get_driver_from_fleet", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"id": 1, "name": "Alice", "license_number": "L1", "phone": "123", "is_active": True}
        response = client.get("/api/v1/admin/fleet/drivers/1")
        assert response.status_code == 200
        assert response.json()["id"] == 1

def test_edit_driver():
    with patch("app.routers.admin_fleet.update_driver_in_fleet", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = {"id": 1, "name": "Alice Updated", "license_number": "L1", "phone": "123", "is_active": True}
        response = client.patch("/api/v1/admin/fleet/drivers/1", json={"name": "Alice Updated"})
        assert response.status_code == 200
        assert response.json()["name"] == "Alice Updated"

def test_deactivate_driver():
    with patch("app.routers.admin_fleet.deactivate_driver", new_callable=AsyncMock) as mock_fleet, \
         patch("app.routers.admin_fleet.keycloak_client.disable_user") as mock_kc:
        
        mock_fleet.return_value = {"id": 1, "auth_user_id": "kc-123", "is_active": False}
        
        response = client.patch("/api/v1/admin/fleet/drivers/1/deactivate")
        
        assert response.status_code == 200
        assert response.json()["is_active"] is False
        mock_kc.assert_called_once_with("kc-123")

# ── Schedule Management ───────────────────────────────────────────────────────

def test_add_schedule():
    with patch("app.routers.admin_fleet.create_schedule", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {"id": 1, "route_id": 1, "scheduled_time": "08:00:00", "day_of_week": 0}
        response = client.post("/api/v1/admin/fleet/schedules", json={"route_id": 1, "scheduled_time": "08:00:00", "day_of_week": 0})
        assert response.status_code == 200
        assert response.json()["route_id"] == 1

# ── Planned Trip Management ───────────────────────────────────────────────────

def test_generate_planned_trips():
    with patch("app.routers.admin_fleet.generate_planned_trips", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {"message": "Generated", "count": 5}
        response = client.post("/api/v1/admin/fleet/planned-trips/generate", params={"target_date": "2026-05-03"})
        assert response.status_code == 200
        assert response.json()["count"] == 5

def test_assign_trip_resources():
    with patch("app.routers.admin_fleet.assign_trip_resources", new_callable=AsyncMock) as mock_assign:
        mock_assign.return_value = {"id": "trip1", "bus_id": 1, "driver_id": 1, "status": "WAITING_AT_DEPOT", "date": "2026-05-03", "schedule_id": 1}
        response = client.patch("/api/v1/admin/fleet/planned-trips/trip1/assign", params={"bus_id": 1, "driver_id": 1})
        assert response.status_code == 200
        assert response.json()["bus_id"] == 1

