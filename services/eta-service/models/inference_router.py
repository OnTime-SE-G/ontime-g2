"""Online AI flow: route inference requests across ETA models with fallbacks."""

from __future__ import annotations

import datetime
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from models._repo_root import repo_root
from models.eta import EtaResult, compute_eta, compute_eta_expressway

logger = logging.getLogger(__name__)

_REPO_ROOT = repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_DEFAULT_MODEL = os.environ.get("ETA_DEFAULT_MODEL", "xgboost")
_WEATHER_COEFFICIENT = float(os.environ.get("ETA_WEATHER_COEFFICIENT", "1.0"))


@dataclass(frozen=True)
class InferenceOutcome:
    result: EtaResult
    model_used: str
    model_version: str | None = None
    run_id: str | None = None
    segment_mode: str = "urban"
    fallback: bool = False


def _segment_model_name(segment_mode: str) -> str:
    if segment_mode == "expressway":
        return os.environ.get("MLFLOW_MODEL_ETA_EXPRESSWAY", "ontime-eta-xgb-expressway")
    return os.environ.get("MLFLOW_MODEL_ETA_URBAN", "ontime-eta-xgb-urban")


def predict(
    distance_m: float,
    speed_ms: float,
    *,
    stops_remaining: int = 1,
    dt: Optional[datetime.datetime] = None,
    model_name: str | None = None,
    segment_mode: str = "urban",
    route_id: str | None = None,
    stop_id: int | None = None,
) -> InferenceOutcome:
    """Run the AI inference chain for a single ETA request."""
    selected = (model_name or _DEFAULT_MODEL).lower().strip()
    segment = (segment_mode or "urban").lower().strip()

    if selected == "physics":
        if segment == "expressway":
            result = compute_eta_expressway(
                distance_m, speed_ms, weather_coefficient=_WEATHER_COEFFICIENT
            )
        else:
            result = compute_eta(distance_m, speed_ms)
        return InferenceOutcome(result=result, model_used="physics", segment_mode=segment)

    if selected == "sarima":
        sarima_outcome = _predict_sarima(
            distance_m,
            speed_ms,
            stops_remaining=stops_remaining,
            dt=dt,
            route_id=route_id,
            stop_id=stop_id,
            segment_mode=segment,
        )
        if sarima_outcome is not None:
            return sarima_outcome
        return _predict_xgboost(
            distance_m,
            speed_ms,
            stops_remaining=stops_remaining,
            dt=dt,
            segment_mode=segment,
        )

    if selected in {"xgboost", "default"}:
        outcome = _predict_xgboost(
            distance_m,
            speed_ms,
            stops_remaining=stops_remaining,
            dt=dt,
            segment_mode=segment,
        )
        return outcome

    result = compute_eta(distance_m, speed_ms)
    return InferenceOutcome(
        result=result,
        model_used="physics",
        segment_mode=segment,
        fallback=True,
    )


def _predict_xgboost(
    distance_m: float,
    speed_ms: float,
    *,
    stops_remaining: int,
    dt: Optional[datetime.datetime],
    segment_mode: str,
) -> InferenceOutcome:
    from models.ml_eta_xgb import predict_eta_xgb

    registered_name = _segment_model_name(segment_mode)
    result = predict_eta_xgb(
        distance_m,
        speed_ms,
        stops_remaining=stops_remaining,
        dt=dt,
        registered_name=registered_name,
    )
    used = "xgboost" if not result.clamped else "physics"
    from models.ml_eta_xgb import get_last_model_metadata

    meta = get_last_model_metadata()
    return InferenceOutcome(
        result=result,
        model_used=used,
        model_version=meta.model_version if meta else None,
        run_id=meta.run_id if meta else None,
        segment_mode=segment_mode,
        fallback=result.clamped,
    )


def _predict_sarima(
    distance_m: float,
    speed_ms: float,
    *,
    stops_remaining: int,
    dt: Optional[datetime.datetime],
    route_id: str | None,
    stop_id: int | None,
    segment_mode: str,
) -> InferenceOutcome | None:
    if not route_id or stop_id is None:
        return None
    try:
        from models.sarima_eta import forecast_eta_sarima

        seconds = forecast_eta_sarima(route_id, int(stop_id))
        if seconds is None:
            return None
        effective_speed = max(speed_ms, 1.4)
        return InferenceOutcome(
            result=EtaResult(
                eta_seconds=max(0.0, float(seconds)),
                distance_m=distance_m,
                speed_ms=effective_speed,
                clamped=False,
            ),
            model_used="sarima",
            segment_mode=segment_mode,
        )
    except Exception as exc:
        logger.warning("SARIMA unavailable, falling back: %s", exc)
        return None
