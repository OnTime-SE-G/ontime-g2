import sys
from pathlib import Path

from fastapi.testclient import TestClient

API_GATEWAY_ROOT = Path(__file__).resolve().parents[1]
if str(API_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(API_GATEWAY_ROOT))

from app.main import app


def test_health_endpoint_returns_expected_shape():
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "api-gateway"
    assert "dependencies" in body
    for dep in ["postgres", "redis", "kafka", "influxdb"]:
        assert dep in body["dependencies"]


def test_metrics_endpoint_is_prometheus_text():
    client = TestClient(app)

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "api_gateway_requests_total" in response.text
    assert "api_gateway_uptime_seconds" in response.text


def test_api_v1_status_endpoint_exists():
    client = TestClient(app)

    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
