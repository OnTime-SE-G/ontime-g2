# tests/integration/test_api.py

from fastapi import HTTPException


def test_full_flow(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.fleet.validate_route_exists",
        lambda route_id: None,
    )

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


def test_assign_route_returns_404_when_route_does_not_exist(client, monkeypatch):
    def route_not_found(route_id):
        raise HTTPException(status_code=404, detail="Route not found")

    monkeypatch.setattr("app.routers.fleet.validate_route_exists", route_not_found)

    create = client.post(
        "/api/v1/fleet/buses",
        json={
            "fleet_code": "BUS-003",
            "plate_number": "NB-9012",
            "capacity": 50
        }
    )
    bus_id = create.json()["id"]

    assign = client.patch(f"/api/v1/fleet/buses/{bus_id}/assign-route/999")

    assert assign.status_code == 404
    assert assign.json()["detail"] == "Route not found"

    bus = client.get(f"/api/v1/fleet/buses/{bus_id}")
    assert bus.json()["route_id"] is None


def test_assign_route_returns_503_when_route_service_is_down(client, monkeypatch):
    def route_service_unavailable(route_id):
        raise HTTPException(status_code=503, detail="Route service unavailable")

    monkeypatch.setattr(
        "app.routers.fleet.validate_route_exists",
        route_service_unavailable,
    )

    create = client.post(
        "/api/v1/fleet/buses",
        json={
            "fleet_code": "BUS-004",
            "plate_number": "NB-3456",
            "capacity": 50
        }
    )
    bus_id = create.json()["id"]

    assign = client.patch(f"/api/v1/fleet/buses/{bus_id}/assign-route/2")

    assert assign.status_code == 503
    assert assign.json()["detail"] == "Route service unavailable"

    bus = client.get(f"/api/v1/fleet/buses/{bus_id}")
    assert bus.json()["route_id"] is None


def test_create_bus_returns_409_for_duplicate_plate_number(client):
    create = client.post(
        "/api/v1/fleet/buses",
        json={
            "fleet_code": "BUS-005",
            "plate_number": "NB-7777",
            "capacity": 50
        }
    )
    assert create.status_code == 200

    duplicate = client.post(
        "/api/v1/fleet/buses",
        json={
            "fleet_code": "BUS-006",
            "plate_number": "NB-7777",
            "capacity": 50
        }
    )

    assert duplicate.status_code == 409
    assert (
        duplicate.json()["detail"]
        == "Bus with this fleet_code or plate_number already exists"
    )


def test_assign_route_returns_404_when_bus_is_missing(client, monkeypatch):
    def should_not_validate_route(route_id):
        raise AssertionError("route validation should not run for missing bus")

    monkeypatch.setattr(
        "app.routers.fleet.validate_route_exists",
        should_not_validate_route,
    )

    response = client.patch("/api/v1/fleet/buses/999999/assign-route/2")

    assert response.status_code == 404
    assert response.json()["detail"] == "Bus not found"


def test_unassign_route_returns_404_when_bus_is_missing(client):
    response = client.patch("/api/v1/fleet/buses/999999/unassign")

    assert response.status_code == 404
    assert response.json()["detail"] == "Bus not found"
