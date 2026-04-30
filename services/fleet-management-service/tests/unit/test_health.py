# tests/unit/test_health.py

def test_health_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "fleet-management-service"