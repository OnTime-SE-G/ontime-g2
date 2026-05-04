# services/websocket-service/main.py
import os
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from redis.asyncio import Redis
from typing import Optional

from connection_manager import ConnectionManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ws-service")

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
FLEET_CHANNEL = os.getenv("FLEET_CHANNEL", "fleet:live")
ETA_CHANNEL = os.getenv("ETA_CHANNEL", "eta:live")

manager = ConnectionManager()

async def redis_listener(app: FastAPI):
    logger.info(f"TASK START: redis_listener looking for {REDIS_URL}")
    retry_count = 0
    while True:
        try:
            logger.info(f"ATTEMPTING REDIS CONNECT: {REDIS_URL}")
            # Ensure redis is initialized
            if not hasattr(app.state, "redis"):
                app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
            
            redis = app.state.redis
            await redis.ping()
            logger.info("REDIS PING SUCCESSFUL")
            
            async with redis.pubsub() as pubsub:
                logger.info(f"SUBSCRIBING TO: {FLEET_CHANNEL}, {ETA_CHANNEL}")
                await pubsub.subscribe(FLEET_CHANNEL, ETA_CHANNEL)
                logger.info("SUBSCRIBE COMMAND SENT")
                
                while True:
                    message = await pubsub.get_message(timeout=1.0)
                    if message and message["type"] == "message":
                        logger.info(f"GOT DATA FROM REDIS: {message}")
                        data = json.loads(message["data"])
                        await manager.broadcast(data)
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"REDIS ERROR: {e}")
            retry_count += 1
            await asyncio.sleep(min(2 ** retry_count, 10))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("FASTAPI STARTUP (LIFESPAN)")
    app.state.redis = Redis.from_url(REDIS_URL, decode_responses=True)
    listener_task = asyncio.create_task(redis_listener(app))
    yield
    # Shutdown
    logger.info("FASTAPI SHUTDOWN (LIFESPAN)")
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass
    if hasattr(app.state, "redis"):
        await app.state.redis.aclose()

app = FastAPI(title="OnTime WebSocket Service", lifespan=lifespan)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    redis_up = False
    try:
        redis = getattr(app.state, "redis", None)
        if redis:
            await redis.ping()
            redis_up = True
    except Exception:
        pass
        
    return {
        "status": "healthy" if redis_up else "degraded",
        "service": "websocket-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "redis": "up" if redis_up else "down"
        }
    }

@app.get("/health/live")
async def live():
    return {
        "status": "alive",
        "service": "websocket-service",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/health/ready")
async def ready():
    redis_up = False
    try:
        redis = getattr(app.state, "redis", None)
        if redis:
            await redis.ping()
            redis_up = True
    except Exception:
        pass
        
    payload = {
        "status": "ready" if redis_up else "not ready",
        "service": "websocket-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "redis": "up" if redis_up else "down"
    }
    
    status_code = status.HTTP_200_OK if redis_up else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)

@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    redis_up = 0
    try:
        redis = getattr(app.state, "redis", None)
        if redis:
            await redis.ping()
            redis_up = 1
    except Exception:
        pass
        
    conn_count = len(manager.active_connections)
    
    prometheus_lines = [
        "# HELP websocket_redis_up Redis connection status (1=up, 0=down)",
        "# TYPE websocket_redis_up gauge",
        f"websocket_redis_up {redis_up}",
        "",
        "# HELP websocket_active_connections Current number of active WebSocket connections",
        "# TYPE websocket_active_connections gauge",
        f"websocket_active_connections {conn_count}"
    ]
    return "\n".join(prometheus_lines)

@app.get("/debug")
async def debug():
    # Direct check to see if we can see the subscription
    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    subs = await redis.execute_command("PUBSUB", "NUMSUB", FLEET_CHANNEL)
    return {
        "channel": FLEET_CHANNEL,
        "subs_info": subs,
        "connections": len(manager.active_connections)
    }

@app.websocket("/v1/live")
async def websocket_endpoint(
    websocket: WebSocket, 
    routeId: Optional[str] = None, 
    busId: Optional[str] = None
):
    # Pass redis for initial state fetching
    redis = getattr(app.state, "redis", None)
    await manager.connect(websocket, route_id=routeId, bus_id=busId, redis=redis)
    logger.info(f"WS CONNECTED: routeId={routeId}, busId={busId}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WS DISCONNECTED: routeId={routeId}, busId={busId}")