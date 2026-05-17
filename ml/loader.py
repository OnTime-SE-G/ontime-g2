"""Load models from MLflow registry with local joblib fallback."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from ml.registry import get_model_uri
from ml.tracking import configure_tracking

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelLoadResult:
    model: Any
    features: list[str] | None
    source: str
    model_name: str
    model_version: str | None
    run_id: str | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_fallback_path(model_name: str) -> Path | None:
    mapping = {
        "ontime-eta-xgb": _repo_root()
        / "services"
        / "eta-service"
        / "models"
        / "training"
        / "eta_model_xgb.joblib",
        "ontime-eta-xgb-urban": _repo_root()
        / "services"
        / "eta-service"
        / "models"
        / "training"
        / "eta_model_xgb.joblib",
        "ontime-eta-xgb-expressway": _repo_root()
        / "services"
        / "eta-service"
        / "models"
        / "training"
        / "eta_model_xgb.joblib",
        "ontime-anomaly-if-behavioral": _repo_root()
        / "services"
        / "anomaly-service"
        / "app"
        / "models"
        / "training"
        / "isolation_forest.joblib",
        "ontime-anomaly-if-spatial": _repo_root()
        / "services"
        / "anomaly-service"
        / "app"
        / "models"
        / "training"
        / "isolation_forest_spatial.joblib",
    }
    path = mapping.get(model_name)
    if path and path.exists():
        return path
    override = os.environ.get("MODEL_ARTIFACT_FALLBACK_PATH")
    if override and Path(override).exists():
        return Path(override)
    return path if path else None


def load_joblib_payload(path: Path) -> ModelLoadResult:
    payload = joblib.load(path)
    if isinstance(payload, dict) and "model" in payload:
        return ModelLoadResult(
            model=payload["model"],
            features=payload.get("features"),
            source=f"joblib:{path}",
            model_name=path.stem,
            model_version=None,
            run_id=None,
        )
    return ModelLoadResult(
        model=payload,
        features=None,
        source=f"joblib:{path}",
        model_name=path.stem,
        model_version=None,
        run_id=None,
    )


@lru_cache(maxsize=16)
def load_predictor(
    model_name: str,
    *,
    stage: str | None = None,
    version: str | None = None,
    fallback_path: str | None = None,
) -> ModelLoadResult:
    """Load a model from MLflow; fall back to local joblib if unavailable."""
    configure_tracking()
    uri = get_model_uri(model_name, stage=stage, version=version)
    try:
        import mlflow.sklearn

        model = mlflow.sklearn.load_model(uri)
        return ModelLoadResult(
            model=model,
            features=None,
            source=f"mlflow:{uri}",
            model_name=model_name,
            model_version=version,
            run_id=None,
        )
    except Exception as exc:
        logger.warning("MLflow load failed for %s (%s): %s", model_name, uri, exc)

    path = Path(fallback_path) if fallback_path else _default_fallback_path(model_name)
    if path is None or not path.exists():
        raise FileNotFoundError(
            f"No model available for {model_name} (MLflow URI {uri}, fallback {path})"
        )
    return load_joblib_payload(path)
