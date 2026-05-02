# tests/unit/test_health.py

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


def test_health_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "fleet-management-service"


def test_health_returns_503_when_database_is_disconnected():
    class DisconnectedDb:
        def execute(self, statement):
            raise RuntimeError("database disconnected")

    def override_get_db():
        yield DisconnectedDb()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    data = response.json()

    assert data["status"] == "error"
    assert data["service"] == "fleet-management-service"
    assert data["database"] == "disconnected"
