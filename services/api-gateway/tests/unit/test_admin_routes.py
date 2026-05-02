import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock

API_GATEWAY_ROOT = Path(__file__).resolve().parents[2]
if str(API_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(API_GATEWAY_ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_route():
    with patch("app.routers.admin_routes.add_route", new_callable=AsyncMock) as mock_add:
        mock_add.return_value = {"message": "Success", "route_id": 1, "route_name": "Test", "stops_inserted": 5}
        files = {"file": ("test.kml", b"<kml></kml>", "application/vnd.google-earth.kml+xml")}
        data = {"route_name": "Test"}
        response = client.post("/api/v1/admin/routes/add-route", data=data, files=files)
        assert response.status_code == 200
        assert response.json()["message"] == "Success"

def test_replace_route():
    with patch("app.routers.admin_routes.update_route", new_callable=AsyncMock) as mock_update:
        mock_update.return_value = {"message": "Success", "route_id": 1, "route_name": "Test", "stops_inserted": 5}
        files = {"file": ("test.kml", b"<kml></kml>", "application/vnd.google-earth.kml+xml")}
        data = {"route_name": "Test"}
        response = client.put("/api/v1/admin/routes/1", data=data, files=files)
        assert response.status_code == 200
        assert response.json()["route_id"] == 1

def test_remove_route():
    with patch("app.routers.admin_routes.delete_route", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = {"message": "Deleted", "route_id": 1}
        response = client.delete("/api/v1/admin/routes/1")
        assert response.status_code == 200
        assert response.json()["message"] == "Deleted"
