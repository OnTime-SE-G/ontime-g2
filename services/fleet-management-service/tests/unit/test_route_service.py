import httpx
import pytest
from fastapi import HTTPException

from app.services.route_service import validate_route_exists


def test_validate_route_exists_allows_existing_route(monkeypatch):
    def fake_get(url, timeout):
        return httpx.Response(200)

    monkeypatch.setattr("app.services.route_service.httpx.get", fake_get)

    validate_route_exists(2)


def test_validate_route_exists_raises_404_for_missing_route(monkeypatch):
    def fake_get(url, timeout):
        return httpx.Response(404)

    monkeypatch.setattr("app.services.route_service.httpx.get", fake_get)

    with pytest.raises(HTTPException) as exc_info:
        validate_route_exists(999)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Route not found"


def test_validate_route_exists_raises_503_when_route_service_is_unavailable(
    monkeypatch,
):
    def fake_get(url, timeout):
        request = httpx.Request("GET", url)
        raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr("app.services.route_service.httpx.get", fake_get)

    with pytest.raises(HTTPException) as exc_info:
        validate_route_exists(2)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Route service unavailable"
