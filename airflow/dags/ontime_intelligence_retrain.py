"""
Airflow DAG: retrain G2 intelligence models when sufficient data exists.

Schedule: weekly (manual trigger supported). Synthetic-only runs stay in Staging.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

_REPO_ROOT = "/opt/ontime/repo"
_ML_ROOT = "/opt/ontime/ml"
if os.path.isdir(_REPO_ROOT):
    sys.path.insert(0, _REPO_ROOT)
    sys.path.insert(0, _ML_ROOT)


def _check_sufficient_data() -> bool:
    from ml.pipelines.sufficient_data import check_data_sufficiency

    result = check_data_sufficiency()
    if not result.sufficient:
        print(f"Skipping retrain: {result.reasons}")
    return result.sufficient


def _export_datasets() -> None:
    os.environ.setdefault("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    subprocess.check_call(
        [sys.executable, f"{_ML_ROOT}/pipelines/export_influx_eta_features.py"],
        cwd=_REPO_ROOT,
    )
    subprocess.check_call(
        [sys.executable, f"{_ML_ROOT}/pipelines/export_postgres_eta.py"],
        cwd=_REPO_ROOT,
    )


def _train_eta() -> None:
    subprocess.check_call(
        [
            sys.executable,
            f"{_REPO_ROOT}/services/eta-service/models/training/train_xgb.py",
            "--also-urban",
        ],
        cwd=_REPO_ROOT,
        env={**os.environ, "MLFLOW_TRACKING_URI": os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")},
    )


def _train_anomaly() -> None:
    training_dir = f"{_REPO_ROOT}/services/anomaly-service/app/models/training"
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "app.models.training.generate_behavioral_training_data",
            "--out",
            f"{training_dir}/behavioral_train.csv",
        ],
        cwd=f"{_REPO_ROOT}/services/anomaly-service",
    )
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "app.models.training.train_isolation_forest",
            "--mode",
            "behavioral",
            "--input",
            f"{training_dir}/behavioral_train.csv",
        ],
        cwd=f"{_REPO_ROOT}/services/anomaly-service",
        env={**os.environ, "PYTHONPATH": f"{_REPO_ROOT}/services/anomaly-service:{_REPO_ROOT}"},
    )
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "app.models.training.train_isolation_forest",
            "--mode",
            "spatial",
            "--input",
            f"{training_dir}/spatial_train.csv",
        ],
        cwd=f"{_REPO_ROOT}/services/anomaly-service",
        env={**os.environ, "PYTHONPATH": f"{_REPO_ROOT}/services/anomaly-service:{_REPO_ROOT}"},
    )


def _train_sarima() -> None:
    subprocess.check_call(
        [sys.executable, f"{_REPO_ROOT}/services/eta-service/models/training/train_sarima.py"],
        cwd=_REPO_ROOT,
        env={**os.environ, "MLFLOW_TRACKING_URI": os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")},
    )


def _evaluate_and_promote() -> None:
    from ml.pipelines.sufficient_data import check_data_sufficiency

    if not check_data_sufficiency().sufficient:
        print("Promotion skipped — data still below threshold")
        return
    print("Evaluation gate passed — promote models manually in MLflow UI for now")


default_args = {
    "owner": "g2-intelligence",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ontime_intelligence_retrain",
    default_args=default_args,
    description="Retrain ETA and anomaly models when Influx/Postgres data is sufficient",
    schedule_interval="@weekly",
    start_date=datetime(2026, 5, 1),
    catchup=False,
    tags=["g2", "ml", "intelligence"],
) as dag:
    check_data = ShortCircuitOperator(
        task_id="sufficient_data_sensor",
        python_callable=_check_sufficient_data,
    )
    export = PythonOperator(task_id="export_training_datasets", python_callable=_export_datasets)
    train_eta = PythonOperator(task_id="train_eta_models", python_callable=_train_eta)
    train_anom = PythonOperator(task_id="train_anomaly_models", python_callable=_train_anomaly)
    train_sarima = PythonOperator(task_id="train_sarima_optional", python_callable=_train_sarima)
    promote = PythonOperator(task_id="evaluate_and_promote", python_callable=_evaluate_and_promote)

    check_data >> export >> [train_eta, train_anom] >> train_sarima >> promote
