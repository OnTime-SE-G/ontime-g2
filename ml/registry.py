"""MLflow model registry helpers."""

from __future__ import annotations

import os
from typing import Any

from ml.tracking import configure_tracking


def register_sklearn_model(
    model: Any,
    registered_name: str,
    *,
    artifact_path: str = "model",
    input_example: Any | None = None,
) -> str:
    import mlflow.sklearn

    configure_tracking()
    model_info = mlflow.sklearn.log_model(
        sk_model=model,
        artifact_path=artifact_path,
        registered_model_name=registered_name,
        input_example=input_example,
    )
    return model_info.model_uri


def register_xgboost_model(
    model: Any,
    registered_name: str,
    *,
    artifact_path: str = "model",
) -> str:
    import mlflow.xgboost

    configure_tracking()
    model_info = mlflow.xgboost.log_model(
        xgb_model=model,
        artifact_path=artifact_path,
        registered_model_name=registered_name,
    )
    return model_info.model_uri


def get_model_uri(
    registered_name: str,
    stage: str | None = None,
    version: str | None = None,
) -> str:
    try:
        import mlflow  # noqa: F401
    except ImportError:
        resolved_stage = stage or os.environ.get("MODEL_STAGE", "Production")
        return f"models:/{registered_name}/{resolved_stage}"

    configure_tracking()
    if version:
        return f"models:/{registered_name}/{version}"
    resolved_stage = stage or os.environ.get("MODEL_STAGE", "Production")
    return f"models:/{registered_name}/{resolved_stage}"


def promote_model(
    registered_name: str,
    version: str,
    stage: str = "Production",
    archive_existing: bool = True,
) -> None:
    from mlflow.tracking import MlflowClient

    configure_tracking()
    client = MlflowClient()
    client.transition_model_version_stage(
        name=registered_name,
        version=version,
        stage=stage,
        archive_existing_versions=archive_existing,
    )
