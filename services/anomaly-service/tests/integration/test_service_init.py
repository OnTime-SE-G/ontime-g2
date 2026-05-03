import pytest
import asyncio
import httpx
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
