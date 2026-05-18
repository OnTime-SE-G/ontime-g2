"""Offline training scaffold for an Isolation Forest anomaly detector.

This script supports two modes:

  behavioral (default)
    Expects a CSV with columns: max_acceleration, min_acceleration,
    speed_variance, heading_variance, average_speed, sample_count
    Writes: isolation_forest.joblib

  spatial
    Expects a CSV with columns: route_deviation_meters, speed_kmh,
    stationary_duration_sec, distance_to_next_stop_m, route_progress_pct
    Writes: isolation_forest_spatial.joblib

Run:
    python -m app.models.training.train_isolation_forest \\
        --mode spatial --input spatial_train.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest

_REPO_ROOT = Path(__file__).resolve().parents[5]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


BEHAVIORAL_FEATURE_COLUMNS = [
    "max_acceleration",
    "min_acceleration",
    "speed_variance",
    "heading_variance",
    "average_speed",
    "sample_count",
]

SPATIAL_FEATURE_COLUMNS = [
    "route_deviation_meters",
    "speed_kmh",
    "stationary_duration_sec",
    "distance_to_next_stop_m",
    "route_progress_pct",
]

_DEFAULT_OUTPUT = {
    "behavioral": "isolation_forest.joblib",
    "spatial": "isolation_forest_spatial.joblib",
}


def train_model(
    csv_path: Path,
    output_path: Path,
    feature_columns: list[str],
    contamination: float = 0.05,
) -> Path:
    frame = pd.read_csv(csv_path)
    missing = [col for col in feature_columns if col not in frame.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
    )
    model.fit(frame[feature_columns].to_numpy())

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train an anomaly-service Isolation Forest model"
    )
    parser.add_argument(
        "--mode",
        choices=["behavioral", "spatial"],
        default="behavioral",
        help="Feature set to train on (default: behavioral)",
    )
    parser.add_argument("--input", required=True, type=Path, help="CSV file with feature vectors")
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        help="Where to write the trained model artifact (defaults per mode)",
    )
    parser.add_argument(
        "--contamination",
        default=0.05,
        type=float,
        help="Expected anomaly fraction in training data (default: 0.05)",
    )
    args = parser.parse_args()

    feature_columns = (
        SPATIAL_FEATURE_COLUMNS if args.mode == "spatial" else BEHAVIORAL_FEATURE_COLUMNS
    )
    output_path = args.output or Path(__file__).with_name(_DEFAULT_OUTPUT[args.mode])

    artifact_path = train_model(args.input, output_path, feature_columns, args.contamination)
    print(f"Saved {args.mode} IsolationForest artifact to {artifact_path}")

    registered_name = (
        "ontime-anomaly-if-spatial"
        if args.mode == "spatial"
        else "ontime-anomaly-if-behavioral"
    )
    try:
        from ml.registry import register_sklearn_model
        from ml.tracking import log_metrics, log_params, start_run

        frame = pd.read_csv(args.input)
        with start_run("ontime-anomaly", run_name=f"train_{args.mode}"):
            log_params(
                {
                    "mode": args.mode,
                    "contamination": args.contamination,
                    "rows": len(frame),
                }
            )
            log_metrics({"training_rows": float(len(frame))})
            register_sklearn_model(
                joblib.load(artifact_path),
                registered_name,
            )
    except Exception as exc:
        print(f"MLflow registration skipped: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
