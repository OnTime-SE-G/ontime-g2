import pytest
import asyncio
import httpx
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import AnomalyService, settings

@pytest.mark.asyncio
async def test_fetch_route_geometries_integration():
    """Test that the service can fetch and parse geometries from a mock endpoint."""
    service = AnomalyService()

    mock_data = [
        {
            "id": "R1",
            "name": "Route 1",
            "geometry": {"type": "LineString", "coordinates": [[80.0, 6.0], [80.0, 7.0]]}
        },
        {
            "id": "R2",
            "name": "Route without geometry",
            "geometry": None
        },
    ]

    # Mock the HTTP response
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_get.return_value = mock_response

        await service.fetch_route_geometries()

        print(f"\n>>> FETCHED ROUTE GEOMETRIES: {service.route_geometries}")

        assert "R1" in service.route_geometries
        assert service.route_geometries["R1"] == [(6.0, 80.0), (7.0, 80.0)]
        assert "R2" not in service.route_geometries

@pytest.mark.asyncio
async def test_health_endpoint_integration():
    """Test that the health server (FastAPI) is correctly configured."""
    from app.health import app
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health/ready")

    print(f"\n>>> HEALTH CHECK RESPONSE: [{response.status_code}] {response.json()}")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "anomaly-service"


@pytest.mark.asyncio
async def test_process_dlq_message_publishes_inactive_trip_alert(monkeypatch):
    service = AnomalyService()
    producer = AsyncMock()
    monkeypatch.setattr(settings, "inactive_trip_dlq_threshold_count", 2)
    monkeypatch.setattr(settings, "inactive_trip_dlq_window_seconds", 60)
    monkeypatch.setattr(settings, "inactive_trip_dlq_cooldown_seconds", 300)

    def build_event(received_at: str) -> bytes:
        return json.dumps(
            {
                "busId": "1",
                "error_type": "INACTIVE_TRIP",
                "error_reason": "No active trip found for bus 1",
                "original_payload": (
                    '{"busId":"1","lat":6.9271,"lon":79.8612,'
                    '"speed":20.0,"timestamp":"2026-05-02T10:00:00Z"}'
                ),
                "received_at": received_at,
            }
        ).encode("utf-8")

    await service.process_dlq_message(build_event("2026-05-02T10:00:00Z"), producer)
    producer.send_and_wait.assert_not_called()

    await service.process_dlq_message(build_event("2026-05-02T10:00:30Z"), producer)

    producer.send_and_wait.assert_awaited_once()
    _, payload = producer.send_and_wait.await_args.args
    alert = json.loads(payload.decode("utf-8"))
    assert alert["anomalyType"] == "TRIP_NOT_STARTED_DEVICE_ACTIVE"
    assert alert["busId"] == "1"
    assert alert["source"] == "transport-telemetry-dlq"
