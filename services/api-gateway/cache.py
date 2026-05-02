# services/api-gateway/cache.py
# Redis caching layer for real-time fleet positions.
# Key prefixes and TTL logic as specified in Issue #20.

import json
import os
from typing import Optional

import redis

# Key prefix conventions
_FLEET_POSITION_PREFIX = "fleet:position:"   # fleet:position:<bus_id>
_FLEET_STATUS_PREFIX = "fleet:status:"       # fleet:status:<bus_id>
_ROUTE_BUSES_PREFIX = "route:buses:"         # route:buses:<route_id>

# TTL values (seconds)
POSITION_TTL = int(os.getenv("CACHE_POSITION_TTL", "30"))   # GPS positions expire quickly
STATUS_TTL = int(os.getenv("CACHE_STATUS_TTL", "60"))        # Bus status slightly longer
ROUTE_BUSES_TTL = int(os.getenv("CACHE_ROUTE_BUSES_TTL", "120"))


def _get_redis_client() -> redis.Redis:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, db=0, decode_responses=True)


# Module-level client (lazy-connected — Redis will raise on first use if unavailable)
_redis: redis.Redis = _get_redis_client()


# ---------------------------------------------------------------------------
# Fleet position cache helpers
# ---------------------------------------------------------------------------

def set_bus_position(bus_id: str, lat: float, lon: float, bearing: float = 0.0) -> None:
    """Cache the real-time GPS position for a bus."""
    key = f"{_FLEET_POSITION_PREFIX}{bus_id}"
    payload = json.dumps({"lat": lat, "lon": lon, "bearing": bearing})
    _redis.setex(key, POSITION_TTL, payload)


def get_bus_position(bus_id: str) -> Optional[dict]:
    """Return the cached GPS position for a bus, or None if not found / expired."""
    key = f"{_FLEET_POSITION_PREFIX}{bus_id}"
    raw = _redis.get(key)
    return json.loads(raw) if raw else None


def set_bus_status(bus_id: str, status: str, occupancy: int = 0) -> None:
    """Cache the real-time status for a bus."""
    key = f"{_FLEET_STATUS_PREFIX}{bus_id}"
    payload = json.dumps({"status": status, "occupancy": occupancy})
    _redis.setex(key, STATUS_TTL, payload)


def get_bus_status(bus_id: str) -> Optional[dict]:
    """Return the cached status for a bus, or None if not found / expired."""
    key = f"{_FLEET_STATUS_PREFIX}{bus_id}"
    raw = _redis.get(key)
    return json.loads(raw) if raw else None


def set_route_buses(route_id: str, bus_ids: list[str]) -> None:
    """Cache the list of bus IDs assigned to a route."""
    key = f"{_ROUTE_BUSES_PREFIX}{route_id}"
    _redis.setex(key, ROUTE_BUSES_TTL, json.dumps(bus_ids))


def get_route_buses(route_id: str) -> Optional[list[str]]:
    """Return cached bus IDs for a route, or None on cache miss."""
    key = f"{_ROUTE_BUSES_PREFIX}{route_id}"
    raw = _redis.get(key)
    return json.loads(raw) if raw else None


def invalidate_bus(bus_id: str) -> None:
    """Remove all cached keys for a bus (position + status)."""
    _redis.delete(
        f"{_FLEET_POSITION_PREFIX}{bus_id}",
        f"{_FLEET_STATUS_PREFIX}{bus_id}",
    )
