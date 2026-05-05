import os
import sys
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import WebSocket

# Add service directory to sys.path
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from main import app, manager

@pytest.fixture
def client():
    """Fixture for TestClient with lifespan support."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def clear_manager():
    """Ensure manager is clean before each test to prevent cross-test interference."""
    manager.active_connections.clear()
    yield

@pytest.fixture
def mock_redis():
    """Fixture to mock Redis client."""
    with patch("main.Redis.from_url") as mock:
        redis_instance = AsyncMock()
        mock.return_value = redis_instance
        redis_instance.ping.return_value = True
        yield redis_instance

def test_health_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"

def test_health_ready_up(client, mock_redis):
    app.state.redis = mock_redis
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

def test_health_ready_down(client, mock_redis):
    mock_redis.ping.side_effect = Exception("Connection error")
    app.state.redis = mock_redis
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not ready"

def test_metrics_endpoint(client, mock_redis):
    app.state.redis = mock_redis
    fake_ws = MagicMock(spec=WebSocket)
    manager.active_connections[fake_ws] = {}
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "websocket_active_connections 1" in response.text

def test_websocket_filtering(client):
    with client.websocket_connect("/v1/live?routeId=R101") as ws:
        msg = {"routeId": "R101", "busId": "B1", "lat": 6.9}
        asyncio.run(manager.broadcast(msg))
        data = ws.receive_json()
        assert data["routeId"] == "R101"

def test_initial_state_fetching(client, mock_redis):
    mock_redis.keys.return_value = ["bus:1:position"]
    mock_redis.mget.return_value = [json.dumps({"busId": "1", "routeId": "R101", "lat": 6.9})]
    app.state.redis = mock_redis
    with client.websocket_connect("/v1/live?routeId=R101") as ws:
        data = ws.receive_json()
        assert data["busId"] == "1"

def test_manager_disconnect_logic():
    """Directly verify the ConnectionManager's disconnect logic."""
    fake_ws = MagicMock(spec=WebSocket)
    manager.active_connections[fake_ws] = {"routeId": None, "busId": None}
    assert len(manager.active_connections) == 1
    
    manager.disconnect(fake_ws)
    assert len(manager.active_connections) == 0

def test_manager_broadcast_error_cleanup():
    """Verify that broadcast cleans up connections that fail to send."""
    fake_ws = MagicMock(spec=WebSocket)
    # Mock send_json to raise an error
    fake_ws.send_json = AsyncMock(side_effect=Exception("Connection lost"))
    
    manager.active_connections[fake_ws] = {"routeId": None, "busId": None}
    
    # This should trigger the cleanup logic inside broadcast
    asyncio.run(manager.broadcast({"test": "data"}))
    
    assert len(manager.active_connections) == 0
