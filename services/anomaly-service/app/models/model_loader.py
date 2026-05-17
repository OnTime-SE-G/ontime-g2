"""Load anomaly ML models via shared MLflow loader."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def load_isolation_model(registered_name: str, *, fallback_path: Path) -> tuple[object | None, str | None]:
    try:
        from ml.loader import load_predictor

        loaded = load_predictor(registered_name, fallback_path=str(fallback_path))
        version = loaded.model_version or loaded.source
        return loaded.model, version
    except Exception as exc:
        logger.debug("MLflow load failed for %s: %s", registered_name, exc)
        if fallback_path.exists():
            import joblib

            return joblib.load(fallback_path), f"joblib:{fallback_path.name}"
        return None, None
