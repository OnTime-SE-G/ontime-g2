from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from consumer import EtaFeatureConsumer
from routers.eta import router as eta_router


logger = logging.getLogger("eta-service")


def _make_redis_client():
    try:
        import redis

        from app.config import settings

        return redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=False)
    except ImportError:
        # Fallback no-op redis-like client for local tests / missing deps
        class _FakeRedis:
            def setex(self, *args, **kwargs):
                return None

            def publish(self, *args, **kwargs):
                return None

        return _FakeRedis()


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = threading.Event()
    redis_client = _make_redis_client()

    # Initialise eta_records schema (idempotent — safe on every startup)
    try:
        from models.eta_db import init_db

        init_db()
        logger.info("eta_db schema initialised")
    except Exception as exc:
        # Non-fatal in dev/CI environments without a Postgres instance
        logger.warning("eta_db init failed (non-fatal in dev): %s", exc)

    # Create consumer but only start the Kafka loop if kafka-python is installed.
    consumer = EtaFeatureConsumer(redis_client)
    consumer_thread: Optional[threading.Thread] = None

    try:
        # Attempt to import kafka to decide whether to run the loop here.
        import kafka  # type: ignore

        consumer_thread = threading.Thread(
            target=consumer.consume_forever, args=(stop_event,), daemon=True
        )
        consumer_thread.start()
        logger.info("ETA consumer thread started")
    except Exception:
        logger.warning("kafka-python not available; ETA consumer not started in this process")

    yield

    # Shutdown
    stop_event.set()
    if consumer_thread is not None:
        consumer_thread.join(timeout=2.0)
        logger.info("ETA consumer thread stopped")


app = FastAPI(title="ETA Service", version="0.1.0", description="ETA computation service", lifespan=lifespan)

app.include_router(eta_router)


@app.get("/")
def root():
    return {"service": "eta-service", "status": "running"}
