"""
ml_eta_xgb.py — XGBoost ETA predictor (Inc 2, K-9).

Loads the trained artifact (eta_model_xgb.joblib) once at import time
and exposes predict_eta_xgb() which mirrors the compute_eta() interface.

Physics sanity clamp: if the XGBoost prediction deviates more than ±80%
from the physics estimate it is replaced by the physics estimate
(guards against extrapolation on unseen feature distributions).
"""

from __future__ import annotations

import datetime
import os
import logging
from functools import lru_cache
from typing import Optional

import joblib
import numpy as np

from models.eta import compute_eta, EtaResult, _MIN_SPEED_MS

logger = logging.getLogger(__name__)

_DEFAULT_ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "training", "eta_model_xgb.joblib"
)

_CLAMP_RATIO = 0.80   # if |xgb - physics| / physics > 80%, fall back to physics


@lru_cache(maxsize=1)
def _load_model():
    """Load the joblib artifact once, cached for the process lifetime."""
    artifact_path = os.getenv("ETA_XGB_ARTIFACT_PATH", _DEFAULT_ARTIFACT_PATH)
    if not os.path.exists(artifact_path):
        raise FileNotFoundError(
            f"XGBoost artifact not found at {artifact_path}. "
            "Run models/training/train_xgb.py first."
        )
    payload = joblib.load(artifact_path)
    logger.info("XGBoost ETA model loaded from %s", artifact_path)
    return payload["model"], payload["features"]


def predict_eta_xgb(
    distance_m: float,
    speed_ms: float,
    stops_remaining: int = 1,
    dt: Optional[datetime.datetime] = None,
) -> EtaResult:
    """Backward-compatible XGBoost ETA API returning only the ETA result."""
    result, _model_used = predict_eta_xgb_with_fallback(
        distance_m,
        speed_ms,
        stops_remaining=stops_remaining,
        dt=dt,
    )
    return result


def predict_eta_xgb_with_fallback(
    distance_m: float,
    speed_ms: float,
    stops_remaining: int = 1,
    dt: Optional[datetime.datetime] = None,
) -> tuple[EtaResult, str]:
    """
    Predict ETA using XGBoost with physics fallback metadata.

    Args:
        distance_m:       Metres from bus to target stop.
        speed_ms:         Current bus speed in m/s.
        stops_remaining:  Number of stops still ahead (including target).
        dt:               Reference datetime for temporal features.
                          Defaults to datetime.datetime.now().

    Returns:
        (EtaResult, model_used), where model_used is the final model that
        supplied the returned ETA: "xgboost" or "physics".
    """
    if distance_m < 0:
        distance_m = 0.0

    # Short-circuit: bus is already at the stop
    if distance_m == 0.0:
        effective_speed = max(speed_ms, _MIN_SPEED_MS)
        return EtaResult(
            eta_seconds=0.0,
            distance_m=0.0,
            speed_ms=effective_speed,
            clamped=(speed_ms < _MIN_SPEED_MS),
        ), "physics"

    if dt is None:
        dt = datetime.datetime.now()

    hour = dt.hour
    dow = dt.weekday()   # 0=Monday … 6=Sunday
    is_weekend = 1 if dow >= 5 else 0

    effective_speed = max(speed_ms, _MIN_SPEED_MS)

    # Physics baseline for sanity clamp
    physics = compute_eta(distance_m, effective_speed)

    try:
        model, features = _load_model()
        row = np.array([[
            distance_m,
            effective_speed,
            hour,
            dow,
            is_weekend,
            max(1, stops_remaining),
        ]], dtype=np.float32)
        xgb_seconds = float(model.predict(row)[0])

        # Sanity clamp — avoid wild extrapolation
        if physics.eta_seconds > 0:
            ratio = abs(xgb_seconds - physics.eta_seconds) / physics.eta_seconds
            if ratio > _CLAMP_RATIO:
                logger.warning(
                    "XGBoost prediction %.1fs deviates %.0f%% from physics %.1fs — clamping",
                    xgb_seconds, ratio * 100, physics.eta_seconds,
                )
                return EtaResult(
                    eta_seconds=physics.eta_seconds,
                    distance_m=distance_m,
                    speed_ms=effective_speed,
                    clamped=True,
                ), "physics"

        xgb_seconds = max(0.0, xgb_seconds)
        return EtaResult(
            eta_seconds=xgb_seconds,
            distance_m=distance_m,
            speed_ms=effective_speed,
            clamped=(speed_ms < _MIN_SPEED_MS),
        ), "xgboost"

    except FileNotFoundError:
        logger.warning("XGBoost artifact missing — falling back to physics model")
        return physics, "physics"
    except Exception as exc:
        logger.error("XGBoost prediction error: %s — falling back to physics model", exc)
        return physics, "physics"
