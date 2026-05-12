from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.anomaly_database_url, pool_pre_ping=True, future=True)
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)
    return _SessionLocal


def init_db() -> None:
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS anomaly_alerts (
                    id BIGSERIAL PRIMARY KEY,
                    bus_id TEXT NOT NULL,
                    trip_id TEXT,
                    route_id TEXT,
                    anomaly_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT,
                    payload JSONB NOT NULL,
                    event_timestamp TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_anomaly_alerts_bus_time
                    ON anomaly_alerts (bus_id, created_at)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_anomaly_alerts_type_time
                    ON anomaly_alerts (anomaly_type, created_at)
                """
            )
        )
    logger.info("anomaly_alerts schema initialised")


def _parse_timestamp(value: Any):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def insert_alert(alert: dict[str, Any]) -> None:
    session = _get_session_factory()()
    try:
        session.execute(
            text(
                """
                INSERT INTO anomaly_alerts (
                    bus_id, trip_id, route_id, anomaly_type, message,
                    severity, payload, event_timestamp
                )
                VALUES (
                    :bus_id, :trip_id, :route_id, :anomaly_type, :message,
                    :severity, CAST(:payload AS JSONB), :event_timestamp
                )
                """
            ),
            {
                "bus_id": str(alert.get("busId", "")),
                "trip_id": alert.get("tripId"),
                "route_id": alert.get("routeId"),
                "anomaly_type": str(alert.get("anomalyType", "UNKNOWN")),
                "message": str(alert.get("message", "")),
                "severity": alert.get("severity"),
                "payload": json.dumps(alert, separators=(",", ":"), sort_keys=True),
                "event_timestamp": _parse_timestamp(alert.get("timestamp")),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
