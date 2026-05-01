import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.main import app


DATABASE_URL = os.getenv("DATABASE_URL")
RUNNING_IN_CI = os.getenv("CI", "").lower() == "true"

VALID_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Test Route</name>
      <LineString>
        <coordinates>
          79.9000,7.0000,0 79.9500,7.0500,0 80.0000,7.1000,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Start Stop</name>
      <Point><coordinates>79.9000,7.0000,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>End Stop</name>
      <Point><coordinates>80.0000,7.1000,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

UPDATED_VALID_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Updated Test Route</name>
      <LineString>
        <coordinates>
          79.9100,7.0100,0 79.9600,7.0600,0 80.0100,7.1100,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Updated Start Stop</name>
      <Point><coordinates>79.9100,7.0100,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Updated Middle Stop</name>
      <Point><coordinates>79.9600,7.0600,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Updated End Stop</name>
      <Point><coordinates>80.0100,7.1100,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""

INVALID_KML = "<kml><Document><Placemark></Document></kml>"

INVALID_ROUTE_SHAPE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Incomplete Route</name>
      <LineString>
        <coordinates>79.9000,7.0000,0</coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Only Stop</name>
      <Point><coordinates>79.9000,7.0000,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def db_is_reachable(database_url: str | None) -> tuple[bool, str | None]:
    if not database_url:
        return False, "DATABASE_URL is not set."

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def fail_or_skip(message: str) -> None:
    if RUNNING_IN_CI:
        pytest.fail(message)

    pytest.skip(message)


@pytest.fixture(scope="module")
def client():
    if not DATABASE_URL:
        fail_or_skip(
            "DATABASE_URL is not set. CI must provide a live test database URL."
        )

    reachable, error = db_is_reachable(DATABASE_URL)
    if not reachable:
        fail_or_skip(
            "Live database is not reachable from DATABASE_URL. "
            f"Start docker compose first or fix CI database setup. Error: {error}"
        )

    with TestClient(app) as c:
        yield c


@pytest.fixture
def uploaded_route_ids(client):
    route_ids: list[int] = []

    yield route_ids

    for route_id in route_ids:
        client.delete(f"/api/v1/admin/routes/{route_id}")


def unique_route_name(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def upload_route(client, route_name: str, kml: str = VALID_KML):
    return client.post(
        "/api/v1/admin/routes/add-route",
        data={"route_name": route_name},
        files={
            "file": (
                "route.kml",
                kml,
                "application/vnd.google-earth.kml+xml",
            )
        },
    )


def update_route(client, route_id: int, route_name: str, kml: str):
    return client.put(
        f"/api/v1/admin/routes/{route_id}",
        data={"route_name": route_name},
        files={
            "file": (
                "route.kml",
                kml,
                "application/vnd.google-earth.kml+xml",
            )
        },
    )


def test_root_endpoint_returns_service_metadata(client):
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "route-service"
    assert data["status"] == "running"
    assert "docs" in data


def test_get_routes_returns_list(client):
    response = client.get("/api/v1/routes")

    assert response.status_code == 200

    data = response.json()

    assert isinstance(data, list)


def test_search_endpoint_returns_valid_shape(client):
    response = client.get(
        "/api/v1/routes/search",
        params={
            "start_lat": 7.0,
            "start_lon": 79.9,
            "end_lat": 7.1,
            "end_lon": 80.0,
            "radius_m": 1000
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "count" in data
    assert "routes" in data
    assert isinstance(data["routes"], list)


def test_created_route_detail_returns_feature_collection(client, uploaded_route_ids):
    create_response = upload_route(
        client,
        unique_route_name("detail-route"),
    )
    assert create_response.status_code == 200

    route_id = create_response.json()["route_id"]
    uploaded_route_ids.append(route_id)

    response = client.get(f"/api/v1/routes/{route_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)
    assert len(data["features"]) == 3


def test_valid_kml_upload_creates_route(client, uploaded_route_ids):
    route_name = unique_route_name("valid-upload")

    response = upload_route(client, route_name)

    assert response.status_code == 200

    data = response.json()
    uploaded_route_ids.append(data["route_id"])

    assert data["message"] == "Route imported successfully"
    assert data["route_name"] == route_name
    assert data["stops_inserted"] == 2

    detail_response = client.get(f"/api/v1/routes/{data['route_id']}")
    assert detail_response.status_code == 200
    assert len(detail_response.json()["features"]) == 3


def test_invalid_kml_upload_returns_400(client):
    response = upload_route(
        client,
        unique_route_name("invalid-upload"),
        INVALID_KML,
    )

    assert response.status_code == 400
    assert "valid KML" in response.json()["detail"]


def test_kml_upload_without_enough_coordinates_and_stops_returns_400(client):
    response = upload_route(
        client,
        unique_route_name("invalid-shape-upload"),
        INVALID_ROUTE_SHAPE_KML,
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "KML must contain at least 2 coordinates and 2 stops"
    )


def test_update_with_invalid_kml_does_not_delete_old_route(
    client,
    uploaded_route_ids,
):
    route_name = unique_route_name("invalid-update-original")
    create_response = upload_route(client, route_name)
    assert create_response.status_code == 200

    route_id = create_response.json()["route_id"]
    uploaded_route_ids.append(route_id)

    response = update_route(
        client,
        route_id,
        unique_route_name("invalid-update-replacement"),
        INVALID_KML,
    )

    assert response.status_code == 400

    detail_response = client.get(f"/api/v1/routes/{route_id}")
    assert detail_response.status_code == 200

    routes_response = client.get("/api/v1/routes")
    assert routes_response.status_code == 200
    assert any(
        route["id"] == route_id and route["name"] == route_name
        for route in routes_response.json()
    )


def test_update_keeps_same_route_id(client, uploaded_route_ids):
    route_name = unique_route_name("update-original")
    create_response = upload_route(client, route_name)
    assert create_response.status_code == 200

    route_id = create_response.json()["route_id"]
    uploaded_route_ids.append(route_id)

    updated_route_name = unique_route_name("update-replacement")
    response = update_route(
        client,
        route_id,
        updated_route_name,
        UPDATED_VALID_KML,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["route_id"] == route_id
    assert data["route_name"] == updated_route_name
    assert data["stops_inserted"] == 3

    detail_response = client.get(f"/api/v1/routes/{route_id}")
    assert detail_response.status_code == 200
    assert len(detail_response.json()["features"]) == 4


def test_route_buses_returns_404_for_missing_route(client):
    routes_response = client.get("/api/v1/routes")
    assert routes_response.status_code == 200

    routes = routes_response.json()
    missing_route_id = max([route["id"] for route in routes], default=0) + 1000000

    response = client.get(f"/api/v1/routes/{missing_route_id}/buses")

    assert response.status_code == 404
    assert response.json()["detail"] == "Route not found"
