# tests/integration/test_api.py

def test_full_flow(client):
    # Create bus
    create = client.post(
        "/api/v1/fleet/buses",
        json={
            "fleet_code": "BUS-002",
            "plate_number": "NB-5678",
            "capacity": 50
        }
    )
    assert create.status_code == 200

    bus_id = create.json()["id"]

    # Assign route
    assign = client.patch(f"/api/v1/fleet/buses/{bus_id}/assign-route/2")
    assert assign.status_code == 200
    assert assign.json()["route_id"] == 2

    # Get by route
    by_route = client.get("/api/v1/fleet/buses/route/2")
    assert by_route.status_code == 200
    assert len(by_route.json()) == 1