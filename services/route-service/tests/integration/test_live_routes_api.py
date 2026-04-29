import os

os.environ["DATABASE_URL"] = (
    "postgresql://postgres:postgres@localhost:5433/ontime_db"
)

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.main import app


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/ontime_db"
)


def db_is_reachable() -> bool:
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@pytest.fixture(scope="module")
def client():
    if not db_is_reachable():
        pytest.skip("Live database is not reachable. Start docker compose first.")

    with TestClient(app) as c:
        yield c


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


def test_first_route_detail_if_exists(client):
    routes_response = client.get("/api/v1/routes")
    routes = routes_response.json()

    if not routes:
        pytest.skip("No routes exist in database.")

    route_id = routes[0]["id"]

    response = client.get(f"/api/v1/routes/{route_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)