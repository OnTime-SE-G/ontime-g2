import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as redis
from app.config import REDIS_URL

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["WebSocket"]
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Handle stale connections
                pass

manager = ConnectionManager()

@router.websocket("/v1/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    
    # Start a subscriber for this specific connection or use a shared one
    # For Increment 1, we'll implement a simple per-connection subscriber
    # In production, we'd use a single background listener that broadcasts to all.
    
    r = redis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("fleet:updates")
    
    try:
        while True:
            # Check for new messages from Redis
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                data = message["data"].decode("utf-8")
                await websocket.send_text(data)
            
            # Keep the loop alive and responsive to disconnects
            await asyncio.sleep(0.1)
            
            # Optional: handle client-to-server messages if needed
            # await websocket.receive_text() 
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        await pubsub.unsubscribe("fleet:updates")
        await r.close()
