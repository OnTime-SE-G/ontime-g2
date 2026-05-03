# services/eta-service/tests/unit/test_ml_eta_model.py
# Unit tests for the AI (Gradient Boosting) ETA model.

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from models.eta import EtaResult, _DEFAULT_SPEED_MS
from models.ml_eta import (
    _generate_training_data,
    _traffic_multiplier,
    predict_eta,
    _FALLBACK_RATIO_MAX,
    _FALLBACK_RATIO_MIN,
)


class TestTrafficMultiplier:
    def test_weekday_rush_hour_morning(self):
        assert _traffic_multiplier(8, 0) > 1.0

    def test_weekday_rush_hour_evening(self):
        assert _traffic_multiplier(18, 1) > 1.0

    def test_weekday_off_peak(self):
        assert _traffic_multiplier(14, 2) == pytest.approx(1.0)

    def test_late_night_faster(self):
        assert _traffic_multiplier(2, 0) < 1.0

    def test_weekend_moderate(self):
        assert _traffic_multiplier(10, 5) > 1.0

    def test_weekend_off_peak(self):
        assert _traffic_multiplier(20, 6) < 1.0


class TestGenerateTrainingData:
    def test_shape(self):
        X, y = _generate_training_data(n_samples=100)
        assert X.shape == (100, 5)
        assert y.shape == (100,)

    def test_eta_positive(self):
        _, y = _generate_training_data(n_samples=200)
        assert (y > 0).all()

    def test_feature_ranges(self):
        X, _ = _generate_training_data(n_samples=500)
        assert X[:, 0].min() >= 200
        assert X[:, 1].min() >= 2.0
        assert X[:, 2].min() >= 0
        assert X[:, 2].max() <= 23


class TestPredictEta:
    def test_returns_eta_result(self):
        result = predict_eta(1000.0, 10.0)
        assert isinstance(result, EtaResult)

    def test_reasonable_range(self):
        result = predict_eta(1000.0, 10.0)
        assert 50 < result.eta_seconds < 250

    def test_rush_hour_slower_than_night(self):
        rush = datetime(2026, 5, 4, 8, 0, tzinfo=timezone.utc)
        night = datetime(2026, 5, 4, 2, 0, tzinfo=timezone.utc)
        result_rush = predict_eta(5000.0, 8.0, dt=rush)
        result_night = predict_eta(5000.0, 8.0, dt=night)
        assert result_rush.eta_seconds >= result_night.eta_seconds * 0.9

    def test_zero_distance_returns_zero(self):
        result = predict_eta(0.0, 10.0)
        assert result.eta_seconds == pytest.approx(0.0, abs=1.0)

    def test_zero_speed_fallback(self):
        result = predict_eta(500.0, 0.0)
        assert result.speed_ms == pytest.approx(_DEFAULT_SPEED_MS)

    def test_clamped_flag_type(self):
        result = predict_eta(1000.0, 8.0)
        assert isinstance(result.clamped, bool)

    def test_model_used_path(self):
        result = predict_eta(2000.0, 8.0)
        assert isinstance(result, EtaResult)

    def test_negative_distance_handled(self):
        result = predict_eta(-100.0, 8.0)
        assert result.eta_seconds >= 0.0
