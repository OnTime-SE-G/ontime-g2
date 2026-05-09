"""Offline training scaffold for an Isolation Forest anomaly detector.

This script expects a CSV file containing one row per summary vector with the
following columns:
- max_acceleration
- min_acceleration
- speed_variance
- heading_variance
- average_speed
- sample_count

It writes a joblib artifact that the runtime AnomalyModel can load when present.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest


FEATURE_COLUMNS = [
    "max_acceleration",
    "min_acceleration",
    "speed_variance",
    "heading_variance",
    "average_speed",
    "sample_count",
]


def train_model(csv_path: Path, output_path: Path, contamination: float = 0.02) -> Path:
    frame = pd.read_csv(csv_path)
    missing = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
    )
    model.fit(frame[FEATURE_COLUMNS])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output_path)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the anomaly-service Isolation Forest model")
    parser.add_argument("--input", required=True, type=Path, help="CSV file with summary vectors")
    parser.add_argument(
        "--output",
        default=Path(__file__).with_name("isolation_forest.joblib"),
        type=Path,
        help="Where to write the trained model artifact",
    )
    parser.add_argument(
        "--contamination",
        default=0.02,
        type=float,
        help="Expected anomaly fraction in the training data",
    )
    args = parser.parse_args()

    artifact_path = train_model(args.input, args.output, args.contamination)
    print(f"Saved IsolationForest artifact to {artifact_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
