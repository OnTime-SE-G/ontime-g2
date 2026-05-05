# tests/unit/test_health.py

from fastapi.testclient import TestClient
from app.database import get_db
from app.main import app
from sqlalchemy import text

def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "fleet-management-service"
    assert data["dependencies"]["database"] == "connected"

def test_health_degraded_when_db_down():
    class DisconnectedDb:
        def execute(self, statement):
            raise RuntimeError("database disconnected")

    def override_get_db():
        yield DisconnectedDb()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["database"] == "disconnected"
    finally:
        app.dependency_overrides.clear()

def test_liveness(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"

def test_readiness_ok(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

def test_readiness_fails_when_db_down():
    class DisconnectedDb:
        def execute(self, statement):
            raise RuntimeError("database disconnected")

    def override_get_db():
        yield DisconnectedDb()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not ready"
    finally:
        app.dependency_overrides.clear()

def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "# HELP" in r.text
