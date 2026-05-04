import asyncio
from unittest.mock import patch

from app.services import fleet_client


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self):
        self.raise_for_status_called = True

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self):
        self.patch_calls = []
        self.response = FakeResponse({"id": 1, "route_id": None})

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def patch(self, url):
        self.patch_calls.append(url)
        return self.response


def test_unassign_route_uses_fleet_patch_endpoint():
    fake_client = FakeAsyncClient()

    with patch.object(fleet_client.httpx, "AsyncClient", return_value=fake_client):
        result = asyncio.run(fleet_client.unassign_route("1"))

    assert result == {"id": 1, "route_id": None}
    assert fake_client.response.raise_for_status_called is True
    assert fake_client.patch_calls == [
        f"{fleet_client.FLEET_SERVICE_URL}/api/v1/fleet/buses/1/unassign"
    ]
