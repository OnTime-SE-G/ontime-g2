"""SARIMA ETA forecaster — production inference path.

Loads pre-trained SARIMAX(1,1,1)(1,1,1,24) artifacts from disk and returns
a point forecast for the given (route_id, stop_id) pair.

Artifact lifecycle
------------------
Training  : services/eta-service/models/training/train_sarima.py (offline CLI)
Artifacts : {SARIMA_ARTIFACT_DIR}/{route_id}_{stop_id}.joblib
Loading   : @lru_cache — artifact loaded once per worker process; evicted only
            on restart.  Cache size 128 covers the expected max distinct
            (route, stop) pairs in production.

Fallback contract
-----------------
forecast_eta_sarima() returns None when:
- No .joblib artifact exists for the (route_id, stop_id) pair
- statsmodels / joblib raises an exception during prediction
Callers must fall back to xgboost → physics in that case.
"""

from __future__ import annotations

import datetime
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Directory containing trained SARIMA artifacts; overridden via env var
# or app/config.py at startup.  Kept as a module-level variable so tests
# can patch it without importing app.config (avoids pydantic-settings deps).
_ARTIFACT_DIR: str = os.getenv("ETA_SARIMA_ARTIFACT_DIR", "sarima_artifacts")


def _artifact_path(route_id: str, stop_id: int) -> str:
    """Return the .joblib path for a (route_id, stop_id) pair."""
    filename = f"{route_id}_{stop_id}.joblib"
    artifact_dir = os.getenv("ETA_SARIMA_ARTIFACT_DIR", _ARTIFACT_DIR)
    return os.path.join(artifact_dir, filename)


@lru_cache(maxsize=128)
def _load_artifact(route_id: str, stop_id: int):
    """Load (and cache) a fitted SARIMAXResults object from disk.

    Returns the fitted model object, or None if the file does not exist.
    Raises on corrupt / incompatible .joblib files so callers know to
    invalidate and retrain.
    """
    path = _artifact_path(route_id, stop_id)
    if not os.path.exists(path):
        logger.debug(
            "No SARIMA artifact at %s — will fall back to XGBoost/physics", path
        )
        return None
    import joblib  # deferred import — not required at module load time

    model = joblib.load(path)
    logger.info("Loaded SARIMA artifact from %s", path)
    return model


def forecast_eta_sarima(
    route_id: str,
    stop_id: int,
    dt: Optional[datetime.datetime] = None,
) -> Optional[float]:
    """Return a SARIMA point-forecast ETA in seconds, or None on failure.

    Parameters
    ----------
    route_id : str
        Route identifier matching the key used during training.
    stop_id  : int
        Stop number on the route.
    dt       : datetime.datetime, optional
        UTC datetime for which to forecast.  Defaults to now().
        Used as the ``start`` and ``end`` argument to model.predict() so
        the seasonal component for the correct hour-of-day is applied.

    Returns
    -------
    float
        Predicted ETA in seconds (≥ 0.0).
    None
        When no artifact exists or prediction raised an exception.
    """
    model = _load_artifact(route_id, stop_id)
    if model is None:
        return None

    forecast_dt = dt if dt is not None else datetime.datetime.now(tz=datetime.timezone.utc)

    try:
        forecast = model.predict(start=forecast_dt, end=forecast_dt)
        eta_s = float(forecast.iloc[0])
        # Clamp to zero — SARIMA can produce negative forecasts near zero
        return max(0.0, eta_s)
    except Exception as exc:  # pragma: no cover — network / statsmodels errors
        logger.error(
            "SARIMA forecast failed for route=%s stop=%s: %s",
            route_id,
            stop_id,
            exc,
        )
        return None
