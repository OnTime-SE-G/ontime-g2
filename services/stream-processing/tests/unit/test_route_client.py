from unittest.mock import MagicMock, patch
import asyncio

from app.utils.route_client import RouteClient


def test_get_all_route_geometries_skips_routes_without_geometry():
    client = RouteClient()
    mock_data = [
        {"id": "R1", "geometry": {"type": "LineString", "coordinates": [[80.0, 6.0], [80.1, 6.1]]}},
        {"id": "R2", "geometry": None},
        {"id": "R3", "geometry": {"type": "LineString", "coordinates": []}},
        {"id": None, "geometry": {"type": "LineString", "coordinates": [[81.0, 7.0], [81.1, 7.1]]}},
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        geometries = asyncio.run(client.get_all_route_geometries())

    assert geometries == {
        "R1": [(6.0, 80.0), (6.1, 80.1)],
    }
