"""MLflow experiment tracking helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

_MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")


def configure_tracking(uri: str | None = None) -> str:
    try:
        import mlflow
    except ImportError:
        return uri or _MLFLOW_URI
    tracking_uri = uri or _MLFLOW_URI
    mlflow.set_tracking_uri(tracking_uri)
    return tracking_uri


@contextmanager
def start_run(
    experiment_name: str,
    run_name: str | None = None,
    tags: dict[str, str] | None = None,
) -> Iterator[Any]:
    try:
        import mlflow
    except ImportError:
        yield None
        return

    configure_tracking()
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as run:
        if tags:
            mlflow.set_tags(tags)
        yield run


def log_params(params: dict[str, Any]) -> None:
    try:
        import mlflow
    except ImportError:
        return
    mlflow.log_params({k: str(v) for k, v in params.items()})


def log_metrics(metrics: dict[str, float], step: int | None = None) -> None:
    try:
        import mlflow
    except ImportError:
        return
    mlflow.log_metrics(metrics, step=step)


def log_model_artifact(local_path: str, artifact_path: str = "model") -> None:
    try:
        import mlflow
    except ImportError:
        return
    mlflow.log_artifact(local_path, artifact_path=artifact_path)
