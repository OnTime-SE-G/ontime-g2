"""Offline SARIMA training CLI for the ETA Service.

Reads historical ETA records from eta_db, fits a
SARIMAX(1,1,1)(1,1,1,24) model per (route_id, stop_id) pair,
evaluates RMSE on the last 24-hour hold-out window, and saves each
fitted model as a .joblib artifact.

Usage
-----
    # From within the eta-service container or a local venv:
    python -m models.training.train_sarima \
        --artifact-dir sarima_artifacts \
        --min-hours   48

Environment
-----------
ETA_DATABASE_URL       : PostgreSQL connection string for eta_db
ETA_SARIMA_MIN_HOURS   : override minimum hours of history (default 48)
ETA_SARIMA_ARTIFACT_DIR: override artifact directory (default sarima_artifacts)

Design notes
------------
- Minimum 48 hours per (route, stop) — 2 full S=24 seasonal cycles
  (required by JPabasara amendment, PR #101)
- Off-route records (off_route=TRUE) are excluded from training
- SARIMAX order=(1,1,1) seasonal_order=(1,1,1,24) fixed per SARIMA plan
- Resampled to hourly mean ETA before fitting
- RMSE evaluated on hold-out = last 24 observations
- Existing artifact overwritten on each run (re-training updates the model)
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit SARIMAX(1,1,1)(1,1,1,24) models from eta_records and save .joblib artifacts."
    )
    parser.add_argument(
        "--artifact-dir",
        default=os.getenv("ETA_SARIMA_ARTIFACT_DIR", "sarima_artifacts"),
        help="Directory to write .joblib artifacts (created if absent)",
    )
    parser.add_argument(
        "--min-hours",
        type=int,
        default=int(os.getenv("ETA_SARIMA_MIN_HOURS", "48")),
        help="Minimum hours of hourly history required to train a model (default 48)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("ETA_DATABASE_URL"),
        help="SQLAlchemy connection string for eta_db (default: ETA_DATABASE_URL env var)",
    )
    return parser.parse_args()


def _fetch_records(database_url: str) -> "pd.DataFrame":
    """Load non-off-route ETA records from eta_db into a DataFrame."""
    import pandas as pd
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, future=True)
    query = text(
        """
        SELECT
            route_id,
            stop_id,
            eta_seconds,
            timestamp
        FROM eta_records
        WHERE off_route = FALSE
          AND route_id IS NOT NULL
          AND stop_id IS NOT NULL
        ORDER BY timestamp
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, parse_dates=["timestamp"])
    logger.info("Fetched %d non-off-route ETA records from eta_db", len(df))
    return df


def _resample_hourly(series: "pd.Series") -> "pd.Series":
    """Resample a timestamp-indexed ETA series to hourly mean."""
    return series.resample("h").mean().dropna()


def _compute_rmse(actual: "pd.Series", predicted: "pd.Series") -> float:
    """Root mean squared error between two aligned Series."""
    import numpy as np

    residuals = actual.values - predicted.values
    return float(math.sqrt(float(np.mean(residuals ** 2))))


def _train_one(
    group: "pd.DataFrame",
    route_id: str,
    stop_id: int,
    min_hours: int,
    artifact_dir: Path,
) -> bool:
    """Fit a SARIMA model for one (route_id, stop_id) pair.

    Returns True on success, False when skipped (insufficient data).
    """
    import joblib
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    series = group.set_index("timestamp")["eta_seconds"].sort_index()
    hourly = _resample_hourly(series)

    if len(hourly) < min_hours:
        logger.warning(
            "Skipping route=%s stop=%d — only %d hourly observations (need %d)",
            route_id,
            stop_id,
            len(hourly),
            min_hours,
        )
        return False

    # Hold-out: last 24 hourly observations
    hold_out_size = min(24, len(hourly) // 4)
    train = hourly.iloc[:-hold_out_size] if hold_out_size > 0 else hourly
    test = hourly.iloc[-hold_out_size:] if hold_out_size > 0 else hourly.iloc[0:0]

    logger.info(
        "Fitting SARIMA route=%s stop=%d  train=%d h  hold-out=%d h",
        route_id,
        stop_id,
        len(train),
        len(test),
    )

    model = SARIMAX(
        train,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 24),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)

    logger.info(
        "  AIC=%.2f  BIC=%.2f  (route=%s stop=%d)",
        fitted.aic,
        fitted.bic,
        route_id,
        stop_id,
    )

    # Evaluate RMSE on hold-out
    if len(test) > 0:
        n_forecast = len(test)
        forecast = fitted.forecast(steps=n_forecast)
        rmse = _compute_rmse(test, forecast)
        logger.info("  hold-out RMSE=%.2f s  (n=%d)", rmse, n_forecast)

    # Persist artifact
    artifact_path = artifact_dir / f"{route_id}_{stop_id}.joblib"
    joblib.dump(fitted, artifact_path)
    logger.info("  Saved artifact → %s", artifact_path)
    return True


def main() -> int:
    """Entry point.  Returns 0 on success, 1 on fatal error."""
    args = _parse_args()

    if not args.database_url:
        logger.error(
            "ETA_DATABASE_URL not set and --database-url not provided. Aborting."
        )
        return 1

    try:
        import pandas  # noqa: F401 — verify dependency early
        import statsmodels  # noqa: F401
        import joblib  # noqa: F401
    except ImportError as exc:
        logger.error("Missing dependency: %s  (run: pip install statsmodels joblib pandas)", exc)
        return 1

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Artifact directory: %s", artifact_dir.resolve())
    logger.info("Minimum hours of history required: %d", args.min_hours)

    # ------------------------------------------------------------------ #
    # Load data                                                            #
    # ------------------------------------------------------------------ #
    try:
        df = _fetch_records(args.database_url)
    except Exception as exc:
        logger.error("Failed to fetch records from eta_db: %s", exc)
        return 1

    if df.empty:
        logger.warning("No records returned — nothing to train.")
        return 0

    # ------------------------------------------------------------------ #
    # Train per (route_id, stop_id)                                       #
    # ------------------------------------------------------------------ #
    groups = df.groupby(["route_id", "stop_id"])
    trained = 0
    skipped = 0

    for (route_id, stop_id), group in groups:
        try:
            ok = _train_one(
                group=group,
                route_id=str(route_id),
                stop_id=int(stop_id),
                min_hours=args.min_hours,
                artifact_dir=artifact_dir,
            )
            if ok:
                trained += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error(
                "Training failed for route=%s stop=%s: %s", route_id, stop_id, exc
            )
            skipped += 1

    logger.info(
        "Training complete — %d models saved, %d groups skipped.", trained, skipped
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
