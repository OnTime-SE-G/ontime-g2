# services/websocket-service/connection_manager.py
from fastapi import WebSocket
from typing import Dict, Set

class ConnectionManager:
    def __init__(self):
        # Maps route_id -> set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, route_id: str):
        await websocket.accept()
        if route_id not in self.active_connections:
            self.active_connections[route_id] = set()
        self.active_connections[route_id].add(websocket)

    def disconnect(self, websocket: WebSocket, route_id: str):
        if route_id in self.active_connections:
            self.active_connections[route_id].discard(websocket)
            if not self.active_connections[route_id]:
                del self.active_connections[route_id]

    async def broadcast_to_route(self, route_id: str, message: dict):
        """Broadcast a message to all clients subscribed to a specific route."""
        if route_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[route_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for dead in dead_connections:
                self.disconnect(dead, route_id)

    async def broadcast_to_all(self, message: dict):
        """Broadcast a message to every single connected client."""
        for route_id in list(self.active_connections.keys()):
            await self.broadcast_to_route(route_id, message)
