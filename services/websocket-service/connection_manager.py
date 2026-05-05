import json
import logging
from fastapi import WebSocket
from typing import Dict, Optional

logger = logging.getLogger("ws-manager")

class ConnectionManager:
    def __init__(self):
        # Maps WebSocket -> Dict[str, Optional[str]] (filters: routeId, busId)
        self.active_connections: Dict[WebSocket, Dict[str, Optional[str]]] = {}

    async def connect(self, websocket: WebSocket, route_id: Optional[str] = None, bus_id: Optional[str] = None, redis=None):
        """Register a new WebSocket connection with optional filters."""
        await websocket.accept()
        self.active_connections[websocket] = {
            "routeId": route_id,
            "busId": bus_id
        }
        
        if redis:
            await self._send_initial_state(websocket, route_id, bus_id, redis)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def broadcast(self, message: dict):
        """Broadcast a message to all clients, applying their individual filters."""
        msg_route_id = str(message.get("routeId", ""))
        msg_bus_id = str(message.get("busId", ""))
        
        dead_connections = []
        # Use list() to avoid "dictionary changed size during iteration"
        for connection, filters in list(self.active_connections.items()):
            f_route = filters.get("routeId")
            f_bus = filters.get("busId")
            
            # Apply filters: if a filter is set, it MUST match the message
            if f_route and f_route != msg_route_id:
                continue
            if f_bus and f_bus != msg_bus_id:
                continue
                
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        
        # Clean up dead connections
        for dead in dead_connections:
            self.disconnect(dead)

    async def _send_initial_state(self, websocket: WebSocket, route_id: Optional[str], bus_id: Optional[str], redis):
        """Fetch current bus positions from Redis and send them to the new client, respecting filters."""
        try:
            # Fetch all keys matching bus:*:position
            keys = await redis.keys("bus:*:position")
            if not keys:
                return

            # Get all positions in one go
            positions = await redis.mget(keys)
            for pos_json in positions:
                if not pos_json:
                    continue
                
                try:
                    data = json.loads(pos_json)
                    target_route = str(data.get("routeId", ""))
                    target_bus = str(data.get("busId", ""))
                    
                    # Apply filters
                    if route_id and route_id != target_route:
                        continue
                    if bus_id and bus_id != target_bus:
                        continue
                        
                    await websocket.send_json(data)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.error(f"Failed to send initial state: {e}")
