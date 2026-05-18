"""
test_ml_eta_xgb.py — Unit tests for the XGBoost ETA predictor (K-10).

Strategy:
  - Train a tiny XGBRegressor on synthetic data in a pytest fixture and
    monkey-patch _load_model so the real artifact file is not required.
  - Test behavioural contracts only (rush-hour > off-peak, zero distance,
    clamp activation, physics fallback) — not numeric accuracy.
"""

import datetime
import os
import sys
import math
import tempfile
import joblib
import pytest
import numpy as np
from unittest.mock import patch
from xgboost import XGBRegressor

# Make sure the eta-service root is on sys.path
_ETA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ETA_ROOT not in sys.path:
    sys.path.insert(0, _ETA_ROOT)

from app.training.generate_data import generate, _traffic_multiplier
from app.prediction.eta import EtaResult, _MIN_SPEED_MS


# ---------------------------------------------------------------------------
# Fixture: train a small model and patch _load_model
# ---------------------------------------------------------------------------

FEATURES = [
    "distance_m", "speed_ms", "hour_of_day",
    "day_of_week", "is_weekend", "stops_remaining", "physics_eta",
]
TARGET = "eta_seconds"


@pytest.fixture(scope="module")
def trained_model():
    """Train a small model on 3000 samples — enough to learn traffic patterns."""
    samples = generate(n_samples=3000, seed=0)
    for sample in samples:
        sample["physics_eta"] = sample["distance_m"] / max(sample["speed_ms"], 1.4)
    X = np.array([[s[f] for f in FEATURES] for s in samples], dtype=np.float32)
    y = np.array([s[TARGET] for s in samples], dtype=np.float32)
    model = XGBRegressor(n_estimators=150, max_depth=6, learning_rate=0.05, random_state=0)
    model.fit(X, y)
    return model, FEATURES


def _load_tuple(trained_model):
    model, features = trained_model
    return model, features, None


@pytest.fixture(autouse=True)
def patch_load_model(trained_model):
    """Replace the cached _load_model with our tiny in-memory model."""
    import app.prediction.ml_eta_xgb as m
    m._load_model.cache_clear()
    with patch.object(m, "_load_model", return_value=_load_tuple(trained_model)):
        yield
    m._load_model.cache_clear()


def _predict(distance_m, speed_ms, stops_remaining=3, hour=10, dow=2):
    from app.prediction.ml_eta_xgb import predict_eta_xgb
    dt = datetime.datetime(2026, 5, 5, hour, 0, 0)
    dt = dt.replace(weekday=None)  # can't set weekday on datetime directly
    # Create a Monday at the given hour
    base = datetime.datetime(2026, 5, 4 + dow, hour, 0)  # 2026-05-04 is Monday
    return predict_eta_xgb(distance_m, speed_ms, stops_remaining=stops_remaining, dt=base)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestZeroDistance:
    def test_zero_distance_returns_zero_eta(self):
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        result = predict_eta_xgb(0.0, 5.0, stops_remaining=2)
        print(f"\n>>> zero distance ETA: {result.eta_seconds}s")
        assert result.eta_seconds == pytest.approx(0.0, abs=1.0)

    def test_negative_distance_treated_as_zero(self):
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        result = predict_eta_xgb(-100.0, 5.0, stops_remaining=2)
        print(f"\n>>> negative distance ETA: {result.eta_seconds}s")
        assert result.eta_seconds == pytest.approx(0.0, abs=1.0)


class TestRushHourVsOffPeak:
    def test_rush_hour_eta_greater_than_off_peak(self):
        """Rush hour (8am weekday) should predict higher ETA than off-peak (2pm weekday)."""
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        dist = 3000.0
        speed = 8.0
        rush = predict_eta_xgb(dist, speed, stops_remaining=5,
                                dt=datetime.datetime(2026, 5, 4, 8, 0))   # Monday 8am
        offpeak = predict_eta_xgb(dist, speed, stops_remaining=5,
                                   dt=datetime.datetime(2026, 5, 4, 14, 0))  # Monday 2pm
        print(f"\n>>> rush ETA: {rush.eta_seconds:.1f}s  off-peak ETA: {offpeak.eta_seconds:.1f}s")
        assert rush.eta_seconds > offpeak.eta_seconds

    def test_evening_rush_eta_greater_than_off_peak(self):
        """Evening rush (6pm weekday) > midday (noon)."""
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        dist = 2000.0
        speed = 6.0
        evening_rush = predict_eta_xgb(dist, speed, stops_remaining=4,
                                        dt=datetime.datetime(2026, 5, 4, 18, 0))
        midday = predict_eta_xgb(dist, speed, stops_remaining=4,
                                  dt=datetime.datetime(2026, 5, 4, 12, 0))
        print(f"\n>>> evening rush: {evening_rush.eta_seconds:.1f}s  midday: {midday.eta_seconds:.1f}s")
        assert evening_rush.eta_seconds > midday.eta_seconds


class TestMinSpeedClamping:
    def test_below_min_speed_sets_clamped_true(self):
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        result = predict_eta_xgb(500.0, 0.3, stops_remaining=2)
        print(f"\n>>> speed 0.3 clamped: {result.clamped}, speed_ms: {result.speed_ms}")
        assert result.clamped is True
        assert result.speed_ms == pytest.approx(_MIN_SPEED_MS)

    def test_speed_ms_field_reflects_effective_speed(self):
        """speed_ms in result should equal the effective (post-clamp) speed."""
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        # Speed well above minimum — result.speed_ms must equal input
        result = predict_eta_xgb(500.0, 8.0, stops_remaining=2)
        assert result.speed_ms == pytest.approx(8.0)


class TestPhysicsFallback:
    def test_artifact_missing_falls_back_to_physics(self):
        """When _load_model raises FileNotFoundError, physics result is returned."""
        import app.prediction.ml_eta_xgb as m
        m._load_model.cache_clear()
        with patch.object(m, "_load_model", side_effect=FileNotFoundError("no artifact")):
            from app.prediction.ml_eta_xgb import predict_eta_xgb
            result = predict_eta_xgb(1000.0, 5.0, stops_remaining=3)
        print(f"\n>>> physics fallback ETA: {result.eta_seconds:.1f}s")
        # Physics: 1000/5 = 200s
        assert result.eta_seconds == pytest.approx(200.0, rel=0.05)

    def test_exception_in_model_falls_back_to_physics(self):
        """Any unexpected exception in predict → physics fallback, no crash."""
        import app.prediction.ml_eta_xgb as m
        m._load_model.cache_clear()
        with patch.object(m, "_load_model", side_effect=RuntimeError("boom")):
            from app.prediction.ml_eta_xgb import predict_eta_xgb
            result = predict_eta_xgb(600.0, 6.0, stops_remaining=2)
        assert result.eta_seconds > 0


class TestSanityClamp:
    def test_wild_prediction_is_clamped_to_physics(self):
        """
        Monkey-patch the model to return a ridiculous value (10× physics).
        Expect the clamp to activate and return the physics estimate.
        """
        import app.prediction.ml_eta_xgb as m
        dist, speed = 500.0, 5.0  # physics = 100s

        class _FakeModel:
            def predict(self, X):
                return np.array([10000.0])   # 10000s vs physics ~100s → >80% deviation

        m._load_model.cache_clear()
        fake = (_FakeModel(), FEATURES, None)
        with patch.object(m, "_load_model", return_value=fake):
            from app.prediction.ml_eta_xgb import predict_eta_xgb
            result = predict_eta_xgb(dist, speed, stops_remaining=2)

        print(f"\n>>> clamped result: {result.eta_seconds:.1f}s  clamped={result.clamped}")
        assert result.clamped is True
        assert result.eta_seconds == pytest.approx(100.0, rel=0.05)


class TestReturnType:
    def test_returns_eta_result_instance(self):
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        result = predict_eta_xgb(1000.0, 8.0, stops_remaining=3)
        assert isinstance(result, EtaResult)

    def test_eta_nonnegative(self):
        from app.prediction.ml_eta_xgb import predict_eta_xgb
        for dist in [0.0, 50.0, 5000.0]:
            result = predict_eta_xgb(dist, 5.0, stops_remaining=2)
            assert result.eta_seconds >= 0.0


class TestGenerateData:
    def test_generates_correct_count(self):
        samples = generate(n_samples=100, seed=1)
        assert len(samples) == 100

    def test_all_required_fields_present(self):
        samples = generate(n_samples=10, seed=1)
        for s in samples:
            for field in ("distance_m", "speed_ms", "hour_of_day",
                          "day_of_week", "is_weekend", "stops_remaining", "eta_seconds"):
                assert field in s

    def test_eta_positive(self):
        samples = generate(n_samples=200, seed=2)
        assert all(s["eta_seconds"] >= 0 for s in samples)

    def test_traffic_multiplier_rush_hour(self):
        assert _traffic_multiplier(8, 1) == pytest.approx(1.25)   # Tuesday 8am
        assert _traffic_multiplier(18, 3) == pytest.approx(1.25)  # Thursday 6pm

    def test_traffic_multiplier_weekend_midday(self):
        assert _traffic_multiplier(12, 6) == pytest.approx(1.15)  # Sunday noon

    def test_traffic_multiplier_off_peak(self):
        assert _traffic_multiplier(10, 2) == pytest.approx(1.00)  # Wednesday 10am
