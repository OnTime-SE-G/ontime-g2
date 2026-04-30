# tests/unit/test_fleet.py

def test_create_bus(client):
    response = client.post(
        "/api/v1/fleet/buses",
        json={
            "fleet_code": "BUS-001",
            "plate_number": "NB-1234",
            "capacity": 40
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["fleet_code"] == "BUS-001"
    assert data["route_id"] is None


def test_get_buses_empty(client):
    response = client.get("/api/v1/fleet/buses")

    assert response.status_code == 200
    assert response.json() == []