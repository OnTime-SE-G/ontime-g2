import os
import sys
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# Add service and tests directory to sys.path
SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from main import app, manager

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_manager():
    """Ensure no stale connections exist between tests."""
    manager.active_connections.clear()
    yield

def test_initial_state_and_live_broadcast_flow():
    """
    INTEGRATION TEST:
    Simulates the flow of populating Redis with a 'SET' key (Initial State)
    followed by a 'PUBLISH' event (Live Broadcast).
    """
    
    # 1. Prepare Mock Redis with 'Stored' Data (Initial State)
    mock_redis = AsyncMock()
    stored_bus_data = {
        "busId": "B-TEST-001", 
        "routeId": "R-101", 
        "lat": 6.9271, 
        "lng": 79.8612,
        "status": "stored_state"
    }
    
    # Mock 'keys' to find our stored position
    mock_redis.keys.return_value = ["bus:B-TEST-001:position"]
    # Mock 'mget' to return the JSON data for that key
    mock_redis.mget.return_value = [json.dumps(stored_bus_data)]
    # Mock 'ping' for health checks
    mock_redis.ping.return_value = True

    # 2. Patch the application to use our Mock Redis
    with patch("main.Redis.from_url", return_value=mock_redis):
        # Inject mock into app state
        app.state.redis = mock_redis
        
        # 3. Connect via WebSocket (Simulating 'npx wscat')
        with client.websocket_connect("/v1/live") as ws:
            
            # --- PHASE A: VERIFY INITIAL STATE ---
            # The client should immediately receive the data stored in Redis keys
            initial_msg = ws.receive_json()
            assert initial_msg["busId"] == "B-TEST-001"
            assert initial_msg["status"] == "stored_state"
            
            # --- PHASE B: VERIFY LIVE BROADCAST ---
            # Simulate a new message arriving via Redis Pub/Sub (simulating 'PUBLISH')
            live_bus_data = {
                "busId": "B-TEST-001", 
                "routeId": "R-101", 
                "lat": 6.9300, 
                "lng": 79.8700,
                "status": "live_update"
            }
            
            # We trigger the manager's broadcast directly 
            # (This is what the redis_listener background task does when it sees a PUBLISH)
            asyncio.run(manager.broadcast(live_bus_data))
            
            # The client should receive the live update
            live_msg = ws.receive_json()
            assert live_msg["busId"] == "B-TEST-001"
            assert live_msg["status"] == "live_update"
            assert live_msg["lat"] == 6.9300

def test_filtering_integration_flow():
    """
    INTEGRATION TEST:
    Verifies that initial state and live updates respect routeId filters.
    """
    mock_redis = AsyncMock()
    
    # Stored data for two different routes
    r101_data = {"busId": "B1", "routeId": "R101", "lat": 1.0}
    r202_data = {"busId": "B2", "routeId": "R202", "lat": 2.0}
    
    mock_redis.keys.return_value = ["bus:B1:position", "bus:B2:position"]
    mock_redis.mget.return_value = [json.dumps(r101_data), json.dumps(r202_data)]
    mock_redis.ping.return_value = True

    with patch("main.Redis.from_url", return_value=mock_redis):
        app.state.redis = mock_redis
        
        # Connect filtering for R101 only
        with client.websocket_connect("/v1/live?routeId=R101") as ws:
            
            # Should receive B1 (R101) but NOT B2 (R202)
            msg = ws.receive_json()
            assert msg["busId"] == "B1"
            
            # Attempt to receive another message (should fail/timeout if we had a timeout, 
            # but here we'll just broadcast a new one to confirm order)
            
            live_r202 = {"busId": "B2", "routeId": "R202", "lat": 3.0} # Should be filtered out
            live_r101 = {"busId": "B1", "routeId": "R101", "lat": 4.0} # Should be received
            
            asyncio.run(manager.broadcast(live_r202))
            asyncio.run(manager.broadcast(live_r101))
            
            # Only the R101 message should come through
            next_msg = ws.receive_json()
            assert next_msg["busId"] == "B1"
            assert next_msg["lat"] == 4.0
