"""
train_xgb.py — Train the XGBoost ETA model (Inc 2, K-8).

Reads (or generates) synthetic training data, trains an XGBRegressor,
prints RMSE + MAE, and saves the artifact as eta_model_xgb.joblib.

Usage (from services/eta-service/ directory):
    python3 models/training/train_xgb.py

Requirements:
    xgboost scikit-learn joblib

Artifact:
    services/eta-service/models/training/eta_model_xgb.joblib
"""

import os
import sys

# Allow running from any working directory
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ETA_SERVICE_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _ETA_SERVICE_ROOT not in sys.path:
    sys.path.insert(0, _ETA_SERVICE_ROOT)

import math
import joblib
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error

from models.training.generate_data import generate

FEATURES = [
    "distance_m",
    "speed_ms",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "stops_remaining",
]
TARGET = "eta_seconds"

ARTIFACT_PATH = os.path.join(_THIS_DIR, "eta_model_xgb.joblib")


def load_or_generate(n_samples: int = 5000, seed: int = 42):
    csv_path = os.path.join(_THIS_DIR, "training_data.csv")
    if os.path.exists(csv_path):
        import csv
        rows = []
        with open(csv_path) as f:
            for row in csv.DictReader(f):
                rows.append({k: float(v) for k, v in row.items()})
        print(f"Loaded {len(rows)} rows from {csv_path}")
        return rows
    print(f"Generating {n_samples} synthetic samples (seed={seed})...")
    return generate(n_samples=n_samples, seed=seed)


def train(n_samples: int = 5000) -> float:
    """Train model, save artifact, return RMSE (seconds)."""
    samples = load_or_generate(n_samples=n_samples)

    X = np.array([[s[f] for f in FEATURES] for s in samples], dtype=np.float32)
    y = np.array([s[TARGET] for s in samples], dtype=np.float32)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

    y_pred = model.predict(X_test)
    rmse = math.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)

    print(f"\nTest RMSE: {rmse:.2f}s  |  MAE: {mae:.2f}s")

    joblib.dump({"model": model, "features": FEATURES}, ARTIFACT_PATH)
    print(f"Artifact saved → {ARTIFACT_PATH}")

    return rmse


if __name__ == "__main__":
    rmse = train()
    if rmse >= 60:
        print(f"WARNING: RMSE {rmse:.1f}s exceeds 60s target — check data quality.")
        sys.exit(1)
    print("Training complete. RMSE within target (< 60s).")
