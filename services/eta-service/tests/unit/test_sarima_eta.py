"""Unit tests for models.sarima_eta — SARIMA ETA forecaster.

Tests cover:
1. Missing artifact → forecast_eta_sarima() returns None (no artifact file)
2. Valid artifact (patched _load_artifact) → returns float >= 0.0
3. lru_cache hit: calling same (route_id, stop_id) twice invokes _load_artifact once
4. Negative forecast output is clamped to 0.0
"""

from __future__ import annotations

import datetime
import sys
import types
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_fitted_model(predict_value: float):
    """Return a mock SARIMAXResults-like object whose predict() returns a Series."""
    class _FakeSeries:
        def __init__(self, values):
            self._values = values

        @property
        def iloc(self):
            return self

        def __getitem__(self, index):
            return self._values[index]

    fake_result = MagicMock()
    fake_result.predict.return_value = _FakeSeries([predict_value])
    return fake_result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestForecastEtaSarima:
    """forecast_eta_sarima() behaviour under various conditions."""

    def _clear_lru_cache(self):
        """Clear _load_artifact lru_cache between tests to avoid cross-test leakage."""
        from models import sarima_eta
        sarima_eta._load_artifact.cache_clear()

    def test_missing_artifact_returns_none(self, tmp_path):
        """When no .joblib file exists, forecast_eta_sarima returns None."""
        self._clear_lru_cache()

        from models import sarima_eta

        # Point artifact dir at an empty temp directory
        original = sarima_eta._ARTIFACT_DIR
        sarima_eta._ARTIFACT_DIR = str(tmp_path)
        try:
            result = sarima_eta.forecast_eta_sarima("route_A", 10)
            assert result is None
        finally:
            sarima_eta._ARTIFACT_DIR = original
            self._clear_lru_cache()

    def test_valid_artifact_returns_float(self):
        """When a fitted model artifact is loaded, forecast returns a float >= 0.0."""
        self._clear_lru_cache()

        expected_eta = 185.3
        fake_model = _make_fake_fitted_model(expected_eta)

        from models import sarima_eta

        with patch.object(sarima_eta, "_load_artifact", return_value=fake_model):
            result = sarima_eta.forecast_eta_sarima("route_B", 5)

        assert isinstance(result, float)
        assert result >= 0.0
        assert abs(result - expected_eta) < 1e-6

    def test_negative_forecast_clamped_to_zero(self):
        """SARIMA can produce negative forecasts near zero — must be clamped to 0.0."""
        self._clear_lru_cache()

        fake_model = _make_fake_fitted_model(-42.7)

        from models import sarima_eta

        with patch.object(sarima_eta, "_load_artifact", return_value=fake_model):
            result = sarima_eta.forecast_eta_sarima("route_C", 3)

        assert result == 0.0

    def test_lru_cache_loads_artifact_once(self, tmp_path):
        """Calling forecast for the same (route_id, stop_id) twice must only
        load the artifact from disk once (lru_cache hit on the second call)."""
        self._clear_lru_cache()

        from models import sarima_eta

        fake_model = _make_fake_fitted_model(99.0)

        # Create an empty file so os.path.exists returns True without needing
        # to joblib.dump a MagicMock (MagicMock class is not picklable by joblib).
        artifact_path = tmp_path / "route_D_7.joblib"
        artifact_path.touch()

        original = sarima_eta._ARTIFACT_DIR
        sarima_eta._ARTIFACT_DIR = str(tmp_path)

        try:
            # _load_artifact imports joblib lazily, so inject a small fake module.
            fake_joblib = types.SimpleNamespace(load=MagicMock(return_value=fake_model))
            with patch.dict(sys.modules, {"joblib": fake_joblib}):
                sarima_eta.forecast_eta_sarima("route_D", 7)
                sarima_eta.forecast_eta_sarima("route_D", 7)

            # lru_cache hit on the second call means joblib.load is invoked once
            assert fake_joblib.load.call_count == 1
        finally:
            sarima_eta._ARTIFACT_DIR = original
            self._clear_lru_cache()

    def test_dt_parameter_is_forwarded_to_predict(self):
        """The dt argument is forwarded as start/end to model.predict()."""
        self._clear_lru_cache()

        fake_model = _make_fake_fitted_model(60.0)
        fixed_dt = datetime.datetime(2026, 5, 15, 8, 0, 0, tzinfo=datetime.timezone.utc)

        from models import sarima_eta

        with patch.object(sarima_eta, "_load_artifact", return_value=fake_model):
            sarima_eta.forecast_eta_sarima("route_E", 12, dt=fixed_dt)

        fake_model.predict.assert_called_once_with(start=fixed_dt, end=fixed_dt)
