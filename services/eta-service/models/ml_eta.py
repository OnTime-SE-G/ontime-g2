# services/eta-service/models/ml_eta.py
# AI-based ETA predictor using a Gradient Boosting Regressor.
#
# The model learns time-of-day and day-of-week traffic patterns on top of the
# physics baseline (distance / speed).  It is bootstrapped with synthetic
# training data that encodes realistic Sri-Lankan urban bus behaviour and can
# be retrained online as real trip records accumulate.
#
# Feature vector: [distance_m, speed_ms, hour_of_day, day_of_week, is_weekend]
# Target:         actual_eta_seconds (physics time x traffic multiplier)
#
# Prediction pipeline:
#   1. Assemble feature vector from inputs.
#   2. Predict with the trained GBR.
#   3. Validate: if prediction is outside a +/-80% band around the physics
#      baseline, fall back to the physics model (guards against extrapolation).
#   4. Return an EtaResult with clamped=False (AI path) or clamped=True
#      (physics fallback).

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.eta import EtaResult, compute_eta, _DEFAULT_SPEED_MS, _MIN_SPEED_MS

# Path where the trained model artefact is persisted (relative to this file)
_MODEL_PATH = Path(__file__).parent / "eta_model.joblib"

# Guard band: if AI prediction diverges more than this factor from physics,
# fall back to physics.
_FALLBACK_RATIO_MAX = 1.8
_FALLBACK_RATIO_MIN = 0.2


# ---------------------------------------------------------------------------
# Synthetic training data generation
# ---------------------------------------------------------------------------

def _traffic_multiplier(hour: int, day_of_week: int) -> float:
    """Return a realistic ETA multiplier for hour-of-day and day."""
    is_weekend = day_of_week >= 5
    if is_weekend:
        if 10 <= hour <= 14:
            return 1.15
        return 0.95

    # Weekday rush hours: 7-9 am and 5-7 pm (17-19)
    if 7 <= hour <= 9:
        return 1.0 + 0.08 * (hour - 6)
    if hour == 10:
        return 1.10
    if 17 <= hour <= 19:
        return 1.0 + 0.10 * (hour - 16)
    if 0 <= hour <= 5:
        return 0.85
    return 1.0


def _generate_training_data(
    n_samples: int = 8000,
    rng: Optional[np.random.Generator] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic (X, y) training pairs.

    Features: [distance_m, speed_ms, hour_of_day, day_of_week, is_weekend]
    Target:   eta_seconds = (distance_m / effective_speed_ms) x traffic_multiplier x noise
    """
    if rng is None:
        rng = np.random.default_rng(42)

    distances = rng.uniform(200, 15_000, n_samples)
    base_speeds = rng.uniform(2.0, 14.0, n_samples)
    hours = rng.integers(0, 24, n_samples)
    days = rng.integers(0, 7, n_samples)
    is_weekends = (days >= 5).astype(float)

    multipliers = np.array([
        _traffic_multiplier(int(h), int(d))
        for h, d in zip(hours, days)
    ])
    noise = rng.normal(loc=1.0, scale=0.05, size=n_samples)
    noise = np.clip(noise, 0.85, 1.20)

    eta = (distances / base_speeds) * multipliers * noise
    X = np.column_stack([distances, base_speeds, hours, days, is_weekends])
    y = eta.astype(np.float64)
    return X, y


# ---------------------------------------------------------------------------
# Model build / load
# ---------------------------------------------------------------------------

def _build_and_train() -> Pipeline:
    X, y = _generate_training_data()
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("gbr", GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )),
    ])
    pipeline.fit(X, y)
    return pipeline


def _load_or_train() -> Pipeline:
    """Load a persisted model if available, otherwise train from scratch."""
    if _MODEL_PATH.exists():
        try:
            return joblib.load(_MODEL_PATH)
        except Exception:
            pass
    model = _build_and_train()
    joblib.dump(model, _MODEL_PATH)
    return model


_model: Optional[Pipeline] = None


def _get_model() -> Pipeline:
    global _model
    if _model is None:
        _model = _load_or_train()
    return _model


def retrain(n_samples: int = 8000) -> None:
    """Retrain the model on fresh data.

    Call from a background task once real trip records are available.
    """
    global _model
    _build_and_train()
    _model = _build_and_train()
    joblib.dump(_model, _MODEL_PATH)


# ---------------------------------------------------------------------------
# Public prediction API
# ---------------------------------------------------------------------------

def predict_eta(
    remaining_distance_m: float,
    speed_ms: float,
    dt: Optional[datetime] = None,
) -> EtaResult:
    """Predict ETA using the AI model, falling back to physics if needed.

    Args:
        remaining_distance_m: Metres from bus to target stop.
        speed_ms:             Current bus speed in m/s.
        dt:                   Observation datetime (default: now UTC).

    Returns:
        EtaResult — clamped=False means AI path was used;
                    clamped=True  means physics fallback was triggered.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    physics = compute_eta(remaining_distance_m, speed_ms)

    if remaining_distance_m <= 0:
        return physics

    effective_speed = speed_ms if speed_ms >= _MIN_SPEED_MS else _DEFAULT_SPEED_MS
    hour = dt.hour
    day = dt.weekday()
    is_weekend = float(day >= 5)

    features = np.array([[
        remaining_distance_m,
        effective_speed,
        hour,
        day,
        is_weekend,
    ]])

    try:
        ai_eta: float = float(_get_model().predict(features)[0])
        ai_eta = max(0.0, ai_eta)
    except Exception:
        return physics

    physics_eta = physics.eta_seconds
    if physics_eta > 0:
        ratio = ai_eta / physics_eta
        if ratio < _FALLBACK_RATIO_MIN or ratio > _FALLBACK_RATIO_MAX:
            return EtaResult(
                eta_seconds=physics_eta,
                distance_m=physics.distance_m,
                speed_ms=physics.speed_ms,
                clamped=True,
            )

    return EtaResult(
        eta_seconds=round(ai_eta, 1),
        distance_m=physics.distance_m,
        speed_ms=effective_speed,
        clamped=False,
    )
