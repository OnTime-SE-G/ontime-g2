"""IsolationForest anomaly detector — production inference module.

Loads a pre-trained sklearn IsolationForest artifact from disk and scores
each GPS telemetry observation against the normal-operation distribution.

Training
--------
Use services/anomaly-service/models/training/train_isolation_forest.py to
fit the model offline from historical GPS telemetry (unsupervised — no
anomaly labels needed). The artifact is saved to ANOMALY_IF_ARTIFACT_DIR.

Feature vector (5 dimensions)
------------------------------
  0  speed_ms            — effective speed in m/s
  1  distance_to_route_m — metres from bus position to nearest route polyline point
  2  heading_delta_deg   — absolute bearing change from previous fix (0–180°)
  3  route_progress_pct  — 0–100 % along the assigned route
  4  hour_of_day         — 0–23 integer (captures time-of-day seasonality)

Fallback contract
-----------------
predict() returns None when:
  - No artifact file exists (model not yet trained)
  - Any exception during scoring
Callers must fall back to the rule-based detector in that case.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

try:
    import joblib
    import numpy as np
except ImportError:  # not installed — feature degrades gracefully
    joblib = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Overridable at startup via env var / app.config
_ARTIFACT_DIR: str = os.getenv("ANOMALY_IF_ARTIFACT_DIR", "if_artifacts")
_ARTIFACT_FILENAME: str = "isolation_forest.joblib"


def _artifact_path() -> str:
    return os.path.join(_ARTIFACT_DIR, _ARTIFACT_FILENAME)


@lru_cache(maxsize=1)
def _load_model():
    """Load (and cache) the fitted IsolationForest from disk.

    Returns the model object, or None if the artifact does not exist.
    Uses lru_cache so the file is read at most once per worker process.
    """
    path = _artifact_path()
    if not os.path.exists(path):
        logger.debug("No IsolationForest artifact at %s — rule-based fallback active", path)
        return None
    try:
        if joblib is None:
            logger.warning("joblib not installed — IsolationForest unavailable")
            return None
        model = joblib.load(path)
        logger.info("Loaded IsolationForest artifact from %s", path)
        return model
    except Exception as exc:
        logger.error("Failed to load IsolationForest artifact %s: %s", path, exc)
        return None


def build_feature_vector(
    speed_ms: float,
    distance_to_route_m: float,
    heading_delta_deg: float,
    route_progress_pct: float,
    hour_of_day: int,
) -> list[float]:
    """Return the 5-element feature vector in training order."""
    return [
        float(speed_ms),
        float(distance_to_route_m),
        float(max(0.0, min(180.0, heading_delta_deg))),
        float(max(0.0, min(100.0, route_progress_pct))),
        float(max(0, min(23, hour_of_day))),
    ]


def predict(
    speed_ms: float,
    distance_to_route_m: float,
    heading_delta_deg: float,
    route_progress_pct: float,
    hour_of_day: int,
) -> Optional[tuple[bool, float]]:
    """Score one telemetry observation against the IsolationForest model.

    Parameters
    ----------
    speed_ms            : effective bus speed in m/s
    distance_to_route_m : perpendicular distance to nearest polyline point (metres)
    heading_delta_deg   : absolute heading change from previous GPS fix (0–180°)
    route_progress_pct  : percentage progress along the route (0–100)
    hour_of_day         : UTC hour of the GPS fix (0–23)

    Returns
    -------
    (is_anomaly, anomaly_score) tuple, where:
        is_anomaly    : True when IsolationForest predicts -1 (outlier)
        anomaly_score : raw decision_function score (more negative = more anomalous)
    None
        When no artifact exists or prediction raises an exception.
    """
    model = _load_model()
    if model is None:
        return None

    features = build_feature_vector(
        speed_ms,
        distance_to_route_m,
        heading_delta_deg,
        route_progress_pct,
        hour_of_day,
    )

    try:
        if np is None:
            logger.warning("numpy not installed — IsolationForest unavailable")
            return None
        X = np.array([features])
        label = int(model.predict(X)[0])          # 1 = normal, -1 = anomaly
        score = float(model.decision_function(X)[0])  # lower = more anomalous
        is_anomaly = label == -1
        return is_anomaly, score
    except Exception as exc:
        logger.error("IsolationForest prediction failed: %s", exc)
        return None
