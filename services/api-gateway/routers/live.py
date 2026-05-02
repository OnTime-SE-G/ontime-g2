# services/api-gateway/routers/live.py
# WebSocket endpoint — subscribes to Redis Pub/Sub channel `fleet:updates`
# and broadcasts each message to connected clients (Issue #23).

import asyncio
import json
import os
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["live"])

_REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
_REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
_FLEET_CHANNEL = "fleet:updates"


async def _subscribe_fleet_updates() -> AsyncGenerator[str, None]:
    """Async generator that yields raw messages from the fleet:updates channel."""
    client = aioredis.Redis(host=_REDIS_HOST, port=_REDIS_PORT, db=0, decode_responses=True)
    async with client.pubsub() as pubsub:
        await pubsub.subscribe(_FLEET_CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield message["data"]
        finally:
            await pubsub.unsubscribe(_FLEET_CHANNEL)
            await client.aclose()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """Stream real-time fleet position updates to the client.

    Each message is a JSON string published to Redis `fleet:updates` by the
    ingestion / stream-processing services.
    """
    await websocket.accept()
    try:
        async for raw in _subscribe_fleet_updates():
            try:
                # Validate it is parseable JSON before forwarding
                payload = json.loads(raw)
                await websocket.send_json(payload)
            except (json.JSONDecodeError, ValueError):
                await websocket.send_text(raw)
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
