# services/eta-service/cache.py
# Redis reader for real-time bus positions published by the ingestion pipeline.

import json
import os
from typing import Optional

import redis

_FLEET_POSITION_PREFIX = "fleet:position:"

_redis: redis.Redis = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
)


def get_bus_position(bus_id: str) -> Optional[dict]:
    """Return the cached GPS position for a bus, or None if not available."""
    raw = _redis.get(f"{_FLEET_POSITION_PREFIX}{bus_id}")
    return json.loads(raw) if raw else None
