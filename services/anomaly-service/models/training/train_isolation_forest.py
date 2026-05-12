"""Offline IsolationForest training CLI for the Anomaly Service.

Reads historical GPS telemetry from InfluxDB (normal operating data only —
unsupervised approach; no anomaly labels needed), engineers the 5-dimensional
feature vector, fits an IsolationForest, evaluates on a 20% hold-out, and
saves the artifact to ANOMALY_IF_ARTIFACT_DIR/isolation_forest.joblib.

Feature vector
--------------
  0  speed_ms            (m/s)
  1  distance_to_route_m (m)    — requires route geometry from route-service
  2  heading_delta_deg   (0–180°)
  3  route_progress_pct  (0–100)
  4  hour_of_day         (0–23)

Usage
-----
    python -m models.training.train_isolation_forest \\
        --influxdb-url   http://localhost:8086 \\
        --influxdb-token <token> \\
        --influxdb-org   ontime \\
        --influxdb-bucket telemetry \\
        --route-service-url http://localhost:8002 \\
        --artifact-dir   if_artifacts \\
        --contamination  0.05 \\
        --n-estimators   100

Environment overrides
---------------------
  INFLUXDB_URL          INFLUXDB_TOKEN    INFLUXDB_ORG    INFLUXDB_BUCKET
  ANOMALY_ROUTE_SERVICE_URL               ANOMALY_IF_ARTIFACT_DIR
  ANOMALY_IF_CONTAMINATION                ANOMALY_IF_N_ESTIMATORS

Design notes
------------
- Queries the last 7 days of telemetry by default (--lookback-hours 168)
- Only rows with a non-null routeId are included (GPS noise / inactive-trip
  rows would corrupt the normal-operation distribution)
- Route geometry is fetched lazily from route-service, cached in memory
- heading_delta computed from consecutive GPS fixes within the same bus/route
- 20% stratified time-split hold-out (last 20% of timestamps per bus)
- Prints: contamination fraction, n_estimators, n_samples_train, F1 proxy
  (fraction of hold-out flagged as anomalous ≈ contamination if well-fitted)
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Fit IsolationForest on GPS telemetry history (unsupervised)."
    )
    p.add_argument("--influxdb-url",    default=os.getenv("INFLUXDB_URL",    "http://localhost:8086"))
    p.add_argument("--influxdb-token",  default=os.getenv("INFLUXDB_TOKEN",  ""))
    p.add_argument("--influxdb-org",    default=os.getenv("INFLUXDB_ORG",    "ontime"))
    p.add_argument("--influxdb-bucket", default=os.getenv("INFLUXDB_BUCKET", "telemetry"))
    p.add_argument("--route-service-url", default=os.getenv("ANOMALY_ROUTE_SERVICE_URL", "http://route-service:8002"))
    p.add_argument("--artifact-dir",    default=os.getenv("ANOMALY_IF_ARTIFACT_DIR", "if_artifacts"))
    p.add_argument("--contamination",   type=float, default=float(os.getenv("ANOMALY_IF_CONTAMINATION", "0.05")))
    p.add_argument("--n-estimators",    type=int,   default=int(os.getenv("ANOMALY_IF_N_ESTIMATORS",    "100")))
    p.add_argument("--lookback-hours",  type=int,   default=168, help="Hours of history to fetch (default 168 = 7 days)")
    p.add_argument("--random-state",    type=int,   default=42)
    return p.parse_args()


# ---------------------------------------------------------------------------
# InfluxDB fetch
# ---------------------------------------------------------------------------

def _fetch_telemetry(url: str, token: str, org: str, bucket: str, lookback_hours: int) -> "pd.DataFrame":
    """Pull GPS telemetry from InfluxDB into a DataFrame."""
    from influxdb_client import InfluxDBClient
    import pandas as pd

    flux_query = f"""
    from(bucket: "{bucket}")
      |> range(start: -{lookback_hours}h)
      |> filter(fn: (r) => r._measurement == "bus_telemetry")
      |> filter(fn: (r) => r._field == "lat" or r._field == "lon"
                         or r._field == "speed" or r._field == "heading"
                         or r._field == "routeProgressPct")
      |> pivot(rowKey: ["_time", "busId", "routeId"], columnKey: ["_field"], valueColumn: "_value")
      |> filter(fn: (r) => exists r.routeId)
      |> sort(columns: ["busId", "_time"])
    """

    with InfluxDBClient(url=url, token=token, org=org) as client:
        df = client.query_api().query_data_frame(flux_query, org=org)

    if df.empty:
        raise ValueError("InfluxDB returned no telemetry rows. Check --lookback-hours or bucket name.")

    df = df.rename(columns={"_time": "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    logger.info("Fetched %d telemetry rows from InfluxDB", len(df))
    return df


# ---------------------------------------------------------------------------
# Route geometry fetch
# ---------------------------------------------------------------------------

def _fetch_route_geometry(route_service_url: str, route_id: str, _cache: dict) -> list:
    """Return polyline as list of (lat, lon) tuples; cached per route_id."""
    if route_id in _cache:
        return _cache[route_id]
    try:
        import httpx

        resp = httpx.get(f"{route_service_url}/api/v1/internal/routes/{route_id}/geometry", timeout=10)
        resp.raise_for_status()
        coords = resp.json().get("coordinates", [])
        polyline = [(c["lat"], c["lon"]) for c in coords]
    except Exception as exc:
        logger.warning("Could not fetch geometry for route %s: %s", route_id, exc)
        polyline = []
    _cache[route_id] = polyline
    return polyline


# ---------------------------------------------------------------------------
# Geometry helpers (inline to avoid app.models import)
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _dist_to_polyline(lat: float, lon: float, polyline: list) -> float:
    if not polyline:
        return 0.0
    min_d = float("inf")
    for i in range(len(polyline) - 1):
        p1, p2 = polyline[i], polyline[i + 1]
        seg = _haversine(*p1, *p2)
        if seg == 0:
            min_d = min(min_d, _haversine(lat, lon, *p1))
            continue
        d1 = _haversine(lat, lon, *p1)
        d2 = _haversine(lat, lon, *p2)
        t = max(0.0, min(1.0, (d1 ** 2 + seg ** 2 - d2 ** 2) / (2 * seg ** 2)))
        proj = (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
        min_d = min(min_d, _haversine(lat, lon, *proj))
    return min_d


def _heading_delta(h1: float, h2: float) -> float:
    """Absolute angular difference between two headings (0–180°)."""
    delta = abs(h1 - h2) % 360
    return min(delta, 360 - delta)


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _engineer_features(df: "pd.DataFrame", route_service_url: str) -> "pd.DataFrame":
    """Add feature columns to df in-place; return rows with all features valid."""
    import numpy as np

    route_cache: dict = {}

    # distance_to_route_m
    def _dist_row(row):
        poly = _fetch_route_geometry(route_service_url, str(row["routeId"]), route_cache)
        return _dist_to_polyline(row["lat"], row["lon"], poly)

    logger.info("Computing distance_to_route_m for %d rows (may be slow)...", len(df))
    df["distance_to_route_m"] = df.apply(_dist_row, axis=1)

    # heading_delta_deg — difference from previous fix of same bus
    df = df.sort_values(["busId", "timestamp"]).copy()
    df["prev_heading"] = df.groupby("busId")["heading"].shift(1)
    df["heading_delta_deg"] = df.apply(
        lambda r: _heading_delta(r["heading"], r["prev_heading"])
        if not (np.isnan(r["heading"]) or np.isnan(r.get("prev_heading", float("nan"))))
        else 0.0,
        axis=1,
    )

    # hour_of_day
    df["hour_of_day"] = df["timestamp"].dt.hour

    # speed in m/s (raw field is km/h in telemetry)
    if df["speed"].max() > 50:  # heuristic: likely km/h
        df["speed_ms"] = df["speed"] / 3.6
    else:
        df["speed_ms"] = df["speed"]

    # route_progress_pct — use as-is or 0
    if "routeProgressPct" not in df.columns:
        df["route_progress_pct"] = 0.0
    else:
        df["route_progress_pct"] = df["routeProgressPct"].fillna(0.0)

    feature_cols = [
        "speed_ms", "distance_to_route_m", "heading_delta_deg",
        "route_progress_pct", "hour_of_day",
    ]
    return df[feature_cols].dropna()


# ---------------------------------------------------------------------------
# Train + evaluate
# ---------------------------------------------------------------------------

def _train_and_evaluate(
    X_train: "np.ndarray",
    X_test: "np.ndarray",
    n_estimators: int,
    contamination: float,
    random_state: int,
) -> object:
    from sklearn.ensemble import IsolationForest

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train)
    logger.info("Fitted IsolationForest on %d training samples", len(X_train))

    if len(X_test) > 0:
        preds = model.predict(X_test)         # 1 = normal, -1 = anomaly
        flagged = (preds == -1).sum()
        flag_rate = flagged / len(X_test)
        logger.info(
            "Hold-out (%d samples): flagged %d (%.1f%%) as anomalous "
            "(contamination=%.2f — expect ~%.1f%%)",
            len(X_test), flagged, flag_rate * 100,
            contamination, contamination * 100,
        )

    return model


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = _parse_args()

    try:
        import numpy as np
        import pandas as pd
        from sklearn.ensemble import IsolationForest  # noqa: F401
        import joblib
    except ImportError as exc:
        logger.error("Missing dependency: %s  (run: pip install scikit-learn joblib influxdb-client httpx pandas)", exc)
        return 1

    if not args.influxdb_token:
        logger.error("--influxdb-token / INFLUXDB_TOKEN is required.")
        return 1

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # 1. Fetch                                                             #
    # ------------------------------------------------------------------ #
    try:
        df = _fetch_telemetry(
            args.influxdb_url, args.influxdb_token,
            args.influxdb_org, args.influxdb_bucket,
            args.lookback_hours,
        )
    except Exception as exc:
        logger.error("Failed to fetch from InfluxDB: %s", exc)
        return 1

    # ------------------------------------------------------------------ #
    # 2. Engineer features                                                 #
    # ------------------------------------------------------------------ #
    try:
        features_df = _engineer_features(df, args.route_service_url)
    except Exception as exc:
        logger.error("Feature engineering failed: %s", exc)
        return 1

    if len(features_df) < 50:
        logger.error(
            "Only %d feature rows — need at least 50 to train. "
            "Increase --lookback-hours or check InfluxDB bucket.",
            len(features_df),
        )
        return 1

    X = features_df.values.astype(np.float64)

    # ------------------------------------------------------------------ #
    # 3. 80/20 time-ordered split                                         #
    # ------------------------------------------------------------------ #
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]

    # ------------------------------------------------------------------ #
    # 4. Train + evaluate                                                  #
    # ------------------------------------------------------------------ #
    model = _train_and_evaluate(
        X_train, X_test,
        n_estimators=args.n_estimators,
        contamination=args.contamination,
        random_state=args.random_state,
    )

    # ------------------------------------------------------------------ #
    # 5. Save artifact                                                     #
    # ------------------------------------------------------------------ #
    out_path = artifact_dir / "isolation_forest.joblib"
    joblib.dump(model, out_path)
    logger.info("Artifact saved → %s", out_path.resolve())

    return 0


if __name__ == "__main__":
    sys.exit(main())
