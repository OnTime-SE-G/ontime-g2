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


def test_create_bus_returns_409_for_duplicate_fleet_code(client):
    bus = {
        "fleet_code": "BUS-001",
        "plate_number": "NB-1234",
        "capacity": 40
    }

    first_response = client.post("/api/v1/fleet/buses", json=bus)
    assert first_response.status_code == 200

    duplicate_response = client.post(
        "/api/v1/fleet/buses",
        json={
            **bus,
            "plate_number": "NB-5678",
        },
    )

    assert duplicate_response.status_code == 409
    assert (
        duplicate_response.json()["detail"]
        == "Bus with this fleet_code or plate_number already exists"
    )


def test_get_buses_empty(client):
    response = client.get("/api/v1/fleet/buses")

    assert response.status_code == 200
    assert response.json() == []
