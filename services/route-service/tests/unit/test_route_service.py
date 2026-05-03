"""Unit tests for route-service endpoints (no real DB required)."""
import sys, os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Add the route-service directory to sys.path so it can be imported without hyphens
_svc_dir = os.path.join(os.path.dirname(__file__), "../..")
sys.path.insert(0, os.path.abspath(_svc_dir))

import sqlalchemy
# Patch create_engine before any import so no real connection is attempted
_orig_create_engine = sqlalchemy.create_engine
sqlalchemy.create_engine = MagicMock(return_value=MagicMock())

from main import app  # noqa: E402

sqlalchemy.create_engine = _orig_create_engine

client = TestClient(app)


def _mock_route(id_=1, name="Route 1", stops=None, buses=None):
    r = MagicMock()
    r.id = id_
    r.name = name
    r.stops = stops or []
    r.buses = buses or []
    return r


def _mock_bus(id_=1, fleet_code="B001", plate="ABC-1234", capacity=50, status="ACTIVE", route_id=1):
    b = MagicMock()
    b.id = id_
    b.fleet_code = fleet_code
    b.plate_number = plate
    b.capacity = capacity
    b.status = status
    b.route_id = route_id
    return b


@pytest.fixture
def mock_db():
    db = MagicMock()
    with patch("routers.routes.get_db", return_value=iter([db])), \
         patch("routers.buses.get_db", return_value=iter([db])):
        yield db


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_routes_empty(mock_db):
    mock_db.query.return_value.options.return_value.all.return_value = []
    resp = client.get("/routes/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_routes_with_data(mock_db):
    mock_db.query.return_value.options.return_value.all.return_value = [
        _mock_route(id_=1, name="Moratuwa–Kadawatha")
    ]
    resp = client.get("/routes/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Moratuwa–Kadawatha"


def test_get_route_not_found(mock_db):
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = None
    resp = client.get("/routes/999")
    assert resp.status_code == 404


def test_get_route_found(mock_db):
    mock_db.query.return_value.options.return_value.filter.return_value.first.return_value = (
        _mock_route(id_=1, name="Route 1")
    )
    resp = client.get("/routes/1")
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


def test_list_buses_empty(mock_db):
    mock_db.query.return_value.all.return_value = []
    resp = client.get("/buses/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_bus_not_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None
    resp = client.get("/buses/999")
    assert resp.status_code == 404


def test_get_bus_found(mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = _mock_bus(id_=5)
    resp = client.get("/buses/5")
    assert resp.status_code == 200
    assert resp.json()["id"] == 5
