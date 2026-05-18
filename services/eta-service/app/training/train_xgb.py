"""
train_xgb.py — Train the XGBoost ETA model (Inc 2, K-8).

Usage (from services/eta-service/ directory):
    python3 models/training/train_xgb.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_ETA_SERVICE_ROOT = _THIS_DIR.parents[1]
_REPO_ROOT = _THIS_DIR.parents[3]
for path in (_ETA_SERVICE_ROOT, _REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from ml.contracts import ETA_XGB_FEATURES
from ml.registry import register_xgboost_model
from ml.tracking import log_metrics, log_model_artifact, log_params, start_run
from app.training.generate_data import generate

FEATURES = ETA_XGB_FEATURES
TARGET = "eta_seconds"
ARTIFACT_PATH = _THIS_DIR / "eta_model_xgb.joblib"


def load_or_generate(n_samples: int = 5000, seed: int = 42):
    csv_path = _THIS_DIR / "training_data.csv"
    if csv_path.exists():
        import csv

        rows = []
        with csv_path.open() as handle:
            for row in csv.DictReader(handle):
                rows.append({k: float(v) for k, v in row.items()})
        print(f"Loaded {len(rows)} rows from {csv_path}")
        return rows
    print(f"Generating {n_samples} synthetic samples (seed={seed})...")
    return generate(n_samples=n_samples, seed=seed)


def train(
    n_samples: int = 5000,
    *,
    registered_name: str = "ontime-eta-xgb",
    promote: bool = False,
) -> float:
    samples = load_or_generate(n_samples=n_samples)
    X = np.array([[s[f] for f in FEATURES] for s in samples], dtype=np.float32)
    y = np.array([s[TARGET] for s in samples], dtype=np.float32)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    params = {
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
    }
    model = XGBRegressor(**params, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

    y_pred = model.predict(X_test)
    rmse = math.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    print(f"\nTest RMSE: {rmse:.2f}s  |  MAE: {mae:.2f}s")

    joblib.dump({"model": model, "features": FEATURES}, ARTIFACT_PATH)
    print(f"Artifact saved → {ARTIFACT_PATH}")

    dataset_hash = hashlib.sha256(json.dumps(samples[:50]).encode()).hexdigest()[:12]
    with start_run("ontime-eta", run_name=f"train_{registered_name}") as _run:
        log_params({**params, "registered_name": registered_name, "n_samples": n_samples})
        log_metrics({"rmse": rmse, "mae": mae})
        log_model_artifact(str(ARTIFACT_PATH), artifact_path="joblib")
        try:
            uri = register_xgboost_model(model, registered_name)
            print(f"Registered in MLflow: {uri}")
            if promote and rmse < 60:
                from ml.registry import promote_model

                version = uri.split("/")[-1]
                promote_model(registered_name, version, stage="Production")
        except Exception as exc:
            print(f"MLflow registration skipped: {exc}")

    return rmse


def main() -> int:
    parser = argparse.ArgumentParser(description="Train XGBoost ETA model")
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--registered-name", default="ontime-eta-xgb")
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--also-urban", action="store_true", help="Register copy as urban model")
    args = parser.parse_args()

    rmse = train(args.samples, registered_name=args.registered_name, promote=args.promote)
    if args.also_urban:
        train(args.samples, registered_name="ontime-eta-xgb-urban", promote=False)

    if rmse >= 60:
        print(
            f"WARNING: RMSE {rmse:.1f}s exceeds 60s target on synthetic holdout "
            "(acceptable for wide-range synthetic data; validate on eta_db before Production promote)."
        )
    else:
        print("Training complete. RMSE within target (< 60s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
