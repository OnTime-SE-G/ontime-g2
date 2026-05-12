"""Unit tests for isolation_forest_model.py."""

import os
import importlib
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_module():
    """Re-import the module so @lru_cache state is cleared between tests."""
    import app.models.isolation_forest_model as m
    importlib.reload(m)
    return m


# ---------------------------------------------------------------------------
# Missing artifact → predict returns None
# ---------------------------------------------------------------------------

class TestMissingArtifact:
    def test_predict_returns_none_when_no_file(self, tmp_path):
        mod = _reload_module()
        # Point artifact dir at an empty directory (file does not exist)
        nonexistent = str(tmp_path / "no_model.joblib")
        with patch.object(mod, "_artifact_path", return_value=nonexistent):
            # Reload lru_cache by reloading the module again
            importlib.reload(mod)
            result = mod.predict(
                speed_ms=10.0,
                distance_to_route_m=5.0,
                heading_delta_deg=15.0,
                route_progress_pct=30.0,
                hour_of_day=8,
            )
        assert result is None

    def test_load_model_returns_none_when_no_file(self, tmp_path):
        mod = _reload_module()
        nonexistent = str(tmp_path / "no_model.joblib")
        with patch.object(mod, "_artifact_path", return_value=nonexistent):
            importlib.reload(mod)
            assert mod._load_model() is None


# ---------------------------------------------------------------------------
# Valid artifact → predict returns (bool, float)
# ---------------------------------------------------------------------------

class TestValidArtifact:
    def _make_mock_model(self, *, label: int, score: float):
        """Return a mock IsolationForest that returns predetermined outputs."""
        import numpy as np

        mock = MagicMock()
        mock.predict.return_value = [label]
        mock.decision_function.return_value = [score]
        return mock

    def test_predict_normal_returns_false(self, tmp_path):
        mod = _reload_module()
        mock_model = self._make_mock_model(label=1, score=0.12)
        with patch.object(mod, "_load_model", return_value=mock_model):
            result = mod.predict(
                speed_ms=8.0,
                distance_to_route_m=12.0,
                heading_delta_deg=5.0,
                route_progress_pct=50.0,
                hour_of_day=14,
            )
        assert result is not None
        is_anomaly, score = result
        assert is_anomaly is False
        assert isinstance(score, float)
        assert score == pytest.approx(0.12)

    def test_predict_anomaly_returns_true(self, tmp_path):
        mod = _reload_module()
        mock_model = self._make_mock_model(label=-1, score=-0.45)
        with patch.object(mod, "_load_model", return_value=mock_model):
            result = mod.predict(
                speed_ms=45.0,
                distance_to_route_m=300.0,
                heading_delta_deg=170.0,
                route_progress_pct=5.0,
                hour_of_day=2,
            )
        assert result is not None
        is_anomaly, score = result
        assert is_anomaly is True
        assert score == pytest.approx(-0.45)

    def test_predict_passes_correct_feature_count(self):
        """predict() must call model.predict with a (1, 5) shaped array."""
        import numpy as np
        mod = _reload_module()
        mock_model = MagicMock()
        mock_model.predict.return_value = [1]
        mock_model.decision_function.return_value = [0.1]

        with patch.object(mod, "_load_model", return_value=mock_model):
            mod.predict(
                speed_ms=10.0,
                distance_to_route_m=20.0,
                heading_delta_deg=30.0,
                route_progress_pct=40.0,
                hour_of_day=10,
            )

        call_args = mock_model.predict.call_args[0][0]
        assert call_args.shape == (1, 5)


# ---------------------------------------------------------------------------
# lru_cache — joblib.load called at most once per process lifetime
# ---------------------------------------------------------------------------

class TestLruCache:
    def test_load_model_cached_after_first_call(self, tmp_path):
        """_load_model() should call joblib.load exactly once, even when called twice."""
        mod = _reload_module()  # fresh module with clear lru_cache
        artifact = tmp_path / "isolation_forest.joblib"
        artifact.write_bytes(b"placeholder")  # file must exist for os.path.exists check

        mock_sklearn_model = MagicMock()

        # Patch _artifact_path to return our tmp file, and joblib.load to avoid
        # actually deserialising the placeholder bytes.
        with patch.object(mod, "_artifact_path", return_value=str(artifact)), \
             patch.object(mod, "joblib") as mock_joblib_mod:
            mock_joblib_mod.load.return_value = mock_sklearn_model
            first  = mod._load_model()
            second = mod._load_model()

        assert first is second
        mock_joblib_mod.load.assert_called_once()


# ---------------------------------------------------------------------------
# build_feature_vector — bounds and order
# ---------------------------------------------------------------------------

class TestBuildFeatureVector:
    def test_returns_five_elements(self):
        mod = _reload_module()
        fv = mod.build_feature_vector(
            speed_ms=5.0,
            distance_to_route_m=20.0,
            heading_delta_deg=45.0,
            route_progress_pct=60.0,
            hour_of_day=9,
        )
        assert len(fv) == 5

    def test_heading_clamped_to_180(self):
        mod = _reload_module()
        fv = mod.build_feature_vector(0.0, 0.0, 270.0, 0.0, 0)
        # 270 → clamped at 180
        assert fv[2] == 180.0

    def test_hour_clamped_to_23(self):
        mod = _reload_module()
        fv = mod.build_feature_vector(0.0, 0.0, 0.0, 0.0, 99)
        assert fv[4] == 23.0

    def test_route_progress_clamped_to_100(self):
        mod = _reload_module()
        fv = mod.build_feature_vector(0.0, 0.0, 0.0, 150.0, 0)
        assert fv[3] == 100.0
