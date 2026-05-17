"""Persistence helpers for ETA records."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from db.models import EtaRecord
from db.session import get_session

logger = logging.getLogger(__name__)


def insert_eta_record(
    snapshot: Mapping[str, Any],
    *,
    stop_id: int,
    model_version: str | None = None,
    segment_mode: str | None = None,
    off_route: bool = False,
) -> None:
    """Insert one ETA record; failures are logged and do not propagate."""
    try:
        with get_session() as session:
            session.add(
                EtaRecord(
                    trip_id=str(snapshot.get("tripId", "")),
                    bus_id=str(snapshot.get("busId", "")),
                    route_id=snapshot.get("routeId"),
                    stop_id=int(stop_id),
                    eta_seconds=float(snapshot.get("etaSeconds", 0.0)),
                    distance_m=float(
                        snapshot.get("distanceToNextStop", snapshot.get("distance_m", 0.0))
                    ),
                    speed_ms=float(snapshot.get("speed", snapshot.get("speed_ms", 0.0))),
                    model_used=str(snapshot.get("modelUsed", "unknown")),
                    model_version=model_version,
                    segment_mode=segment_mode,
                    off_route=off_route,
                )
            )
    except Exception as exc:
        logger.error("eta_db insert failed (non-fatal): %s", exc)
