# services/websocket-service/main.py
import os
import asyncio
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from connection_manager import ConnectionManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ws-service")

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
FLEET_CHANNEL = os.getenv("FLEET_CHANNEL", "fleet:updates")

app = FastAPI(title="OnTime WebSocket Service")
manager = ConnectionManager()

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def redis_listener():
    logger.info(f"TASK START: redis_listener looking for {REDIS_URL}")
    retry_count = 0
    while True:
        try:
            logger.info(f"ATTEMPTING REDIS CONNECT: {REDIS_URL}")
            redis = Redis.from_url(REDIS_URL, decode_responses=True)
            await redis.ping()
            logger.info("REDIS PING SUCCESSFUL")
            
            async with redis.pubsub() as pubsub:
                logger.info(f"SUBSCRIBING TO: {FLEET_CHANNEL}")
                await pubsub.subscribe(FLEET_CHANNEL)
                logger.info("SUBSCRIBE COMMAND SENT")
                
                while True:
                    # Removed ignore_subscribe_metadata for compatibility
                    message = await pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        logger.info(f"GOT DATA FROM REDIS: {message}")
                        data = json.loads(message["data"])
                        route_id = str(data.get("routeId", ""))
                        if route_id:
                            await manager.broadcast_to_route(route_id, data)
                        else:
                            await manager.broadcast_to_all(data)
                    await asyncio.sleep(0.1) # Tiny sleep to prevent CPU spiking
        except Exception as e:
            logger.error(f"REDIS ERROR: {e}")
            retry_count += 1
            await asyncio.sleep(min(2 ** retry_count, 10))

@app.on_event("startup")
async def startup():
    logger.info("FASTAPI STARTUP EVENT TRIGGERED")
    asyncio.create_task(redis_listener())

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/debug")
async def debug():
    # Direct check to see if we can see the subscription
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    subs = await redis.execute_command("PUBSUB", "NUMSUB", FLEET_CHANNEL)
    return {
        "channel": FLEET_CHANNEL,
        "subs_info": subs,
        "connections": list(manager.active_connections.keys())
    }

@app.websocket("/ws/{route_id}")
async def websocket_endpoint(websocket: WebSocket, route_id: str):
    await manager.connect(websocket, route_id)
    logger.info(f"WS CONNECTED: {route_id}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, route_id)
        logger.info(f"WS DISCONNECTED: {route_id}")