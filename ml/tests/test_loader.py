"""Unit tests for ML loader fallback."""

from pathlib import Path

import pytest

from ml.loader import load_joblib_payload


def test_load_eta_joblib_fallback():
    path = (
        Path(__file__).resolve().parents[2]
        / "services"
        / "eta-service"
        / "models"
        / "training"
        / "eta_model_xgb.joblib"
    )
    if not path.exists():
        pytest.skip("eta_model_xgb.joblib not present")
    loaded = load_joblib_payload(path)
    assert loaded.model is not None
    assert loaded.features is not None
    assert "physics_eta" in loaded.features
