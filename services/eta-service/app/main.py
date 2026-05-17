from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from app.config import settings
from app.consumers.eta_consumer import EtaFeatureConsumer
from app.database.connection import init_db
from app.api.endpoints import router as eta_router

logger = logging.getLogger("eta-service")


def _make_redis_client():
    try:
        import redis

        return redis.Redis(host="redis", port=6379, decode_responses=False)
    except Exception:

        class _FakeRedis:
            def setex(self, *args, **kwargs):
                return None

            def publish(self, *args, **kwargs):
                return None

            def get(self, *args, **kwargs):
                return None

        return _FakeRedis()


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = threading.Event()
    try:
        init_db()
        logger.info("eta_db initialized")
    except Exception as exc:
        logger.warning("eta_db init failed (non-fatal): %s", exc)

    redis_client = _make_redis_client()
    consumer = EtaFeatureConsumer(
        redis_client,
        default_model=settings.default_model,
        snapshot_ttl_seconds=settings.eta_snapshot_ttl_seconds,
    )
    consumer_thread: Optional[threading.Thread] = None

    try:
        import kafka  # noqa: F401

        consumer_thread = threading.Thread(
            target=consumer.consume_forever, args=(stop_event,), daemon=True
        )
        consumer_thread.start()
        logger.info("ETA consumer thread started")
    except Exception:
        logger.warning("kafka-python not available; ETA consumer not started in this process")

    yield

    stop_event.set()
    if consumer_thread is not None:
        consumer_thread.join(timeout=2.0)
        logger.info("ETA consumer thread stopped")


app = FastAPI(
    title="ETA Service",
    version="0.2.0",
    description="ETA computation service with MLflow-backed models",
    lifespan=lifespan,
)

app.include_router(eta_router)


@app.get("/")
def root():
    return {"service": "eta-service", "status": "running", "default_model": settings.default_model}


@app.get("/health")
def health():
    return {"status": "ok"}
