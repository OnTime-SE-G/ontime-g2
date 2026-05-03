# tests/unit/test_fleet.py
from unittest.mock import patch

def _create_bus(client, fleet_code="BUS-001", plate="NB-1234"):
    r = client.post(
        "/api/v1/fleet/buses",
        json={"fleet_code": fleet_code, "plate_number": plate, "capacity": 40},
    )
    assert r.status_code == 200
    return r.json()

def test_create_bus(client):
    data = _create_bus(client)
    assert data["fleet_code"] == "BUS-001"
    assert data["route_id"] is None

def test_create_bus_returns_409_for_duplicate_fleet_code(client):
    bus = {
        "fleet_code": "BUS-001",
        "plate_number": "NB-1234",
        "capacity": 40
    }
    client.post("/api/v1/fleet/buses", json=bus)
    
    duplicate_response = client.post(
        "/api/v1/fleet/buses",
        json={**bus, "plate_number": "NB-5678"},
    )
    assert duplicate_response.status_code == 409

def test_get_buses_empty(client):
    response = client.get("/api/v1/fleet/buses")
    assert response.status_code == 200
    assert response.json() == []

def test_assign_route(client):
    bus = _create_bus(client)
    bus_id = bus["id"]
    
    with patch("app.services.route_service.validate_route_exists", return_value=None):
        r = client.patch(f"/api/v1/fleet/buses/{bus_id}/assign-route/101")
        assert r.status_code == 200
        assert r.json()["route_id"] == 101

def test_unassign_route(client):
    bus = _create_bus(client)
    bus_id = bus["id"]
    
    with patch("app.services.route_service.validate_route_exists", return_value=None):
        client.patch(f"/api/v1/fleet/buses/{bus_id}/assign-route/101")
    
    r = client.patch(f"/api/v1/fleet/buses/{bus_id}/unassign")
    assert r.status_code == 200
    assert r.json()["route_id"] is None

def test_get_buses_by_route(client):
    bus1 = _create_bus(client, "B1", "P1")
    bus2 = _create_bus(client, "B2", "P2")
    
    with patch("app.services.route_service.validate_route_exists", return_value=None):
        client.patch(f"/api/v1/fleet/buses/{bus1['id']}/assign-route/202")
    
    r = client.get("/api/v1/fleet/buses/route/202")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["fleet_code"] == "B1"
