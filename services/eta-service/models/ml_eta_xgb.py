"""
ml_eta_xgb.py — XGBoost ETA predictor (Inc 2, K-9).

Loads model from MLflow registry with local joblib fallback.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np

from models.eta import compute_eta, EtaResult, _MIN_SPEED_MS
from ml.contracts import ETA_XGB_FEATURES
from ml.loader import ModelLoadResult, load_predictor

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_ARTIFACT_PATH = Path(__file__).resolve().parent / "training" / "eta_model_xgb.joblib"
_CLAMP_RATIO = 0.80
_DEFAULT_REGISTERED_NAME = os.environ.get("MLFLOW_MODEL_ETA", "ontime-eta-xgb")

_last_load_meta: ModelLoadResult | None = None


@lru_cache(maxsize=4)
def _load_model(registered_name: str = _DEFAULT_REGISTERED_NAME) -> tuple[object, list[str], ModelLoadResult]:
    global _last_load_meta
    fallback = os.environ.get("MODEL_ARTIFACT_FALLBACK_PATH") or str(_ARTIFACT_PATH)
    loaded = load_predictor(registered_name, fallback_path=fallback)
    features = loaded.features or ETA_XGB_FEATURES
    _last_load_meta = loaded
    logger.info("XGBoost ETA model loaded from %s", loaded.source)
    return loaded.model, features, loaded


def predict_eta_xgb(
    distance_m: float,
    speed_ms: float,
    stops_remaining: int = 1,
    dt: Optional[datetime.datetime] = None,
    *,
    registered_name: str | None = None,
) -> EtaResult:
    """Predict ETA using XGBoost with physics sanity clamp."""
    if distance_m < 0:
        distance_m = 0.0

    if distance_m == 0.0:
        effective_speed = max(speed_ms, _MIN_SPEED_MS)
        return EtaResult(
            eta_seconds=0.0,
            distance_m=0.0,
            speed_ms=effective_speed,
            clamped=(speed_ms < _MIN_SPEED_MS),
        )

    if dt is None:
        dt = datetime.datetime.now()

    hour = dt.hour
    dow = dt.weekday()
    is_weekend = 1 if dow >= 5 else 0
    effective_speed = max(speed_ms, _MIN_SPEED_MS)
    physics = compute_eta(distance_m, effective_speed)

    name = registered_name or _DEFAULT_REGISTERED_NAME
    try:
        loaded = _load_model(name)
        if len(loaded) == 3:
            model, features, _meta = loaded
        else:
            model, features = loaded
            _meta = None
        physics_eta_raw = physics.eta_seconds
        feature_values = {
            "distance_m": distance_m,
            "speed_ms": effective_speed,
            "hour_of_day": hour,
            "day_of_week": dow,
            "is_weekend": is_weekend,
            "stops_remaining": max(1, stops_remaining),
            "physics_eta": physics_eta_raw,
        }
        row = np.array([[feature_values.get(f, 0.0) for f in features]], dtype=np.float32)
        xgb_seconds = float(model.predict(row)[0])

        if physics.eta_seconds > 0:
            ratio = abs(xgb_seconds - physics.eta_seconds) / physics.eta_seconds
            if ratio > _CLAMP_RATIO:
                logger.warning(
                    "XGBoost prediction %.1fs deviates %.0f%% from physics %.1fs — clamping",
                    xgb_seconds,
                    ratio * 100,
                    physics.eta_seconds,
                )
                return EtaResult(
                    eta_seconds=physics.eta_seconds,
                    distance_m=distance_m,
                    speed_ms=effective_speed,
                    clamped=True,
                )

        return EtaResult(
            eta_seconds=max(0.0, xgb_seconds),
            distance_m=distance_m,
            speed_ms=effective_speed,
            clamped=(speed_ms < _MIN_SPEED_MS),
        )
    except FileNotFoundError:
        logger.warning("XGBoost artifact missing — falling back to physics model")
        return physics
    except Exception as exc:
        logger.error("XGBoost prediction error: %s — falling back to physics model", exc)
        return physics


def get_last_model_metadata() -> ModelLoadResult | None:
    return _last_load_meta
