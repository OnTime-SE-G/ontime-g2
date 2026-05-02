# services/api-gateway/tests/unit/test_eta_model.py
# Unit tests for the physics-heuristic ETA model.

import sys
import os

# Make the api-gateway root importable without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from models.eta import EtaResult, compute_eta, _DEFAULT_SPEED_MS, _MIN_SPEED_MS


class TestComputeEta:
    def test_normal_speed_and_distance(self):
        result = compute_eta(1000.0, 10.0)
        assert result.eta_seconds == pytest.approx(100.0)
        assert result.distance_m == 1000.0
        assert result.speed_ms == 10.0
        assert result.clamped is False

    def test_zero_speed_uses_default(self):
        result = compute_eta(500.0, 0.0)
        assert result.clamped is True
        assert result.speed_ms == pytest.approx(_DEFAULT_SPEED_MS)
        assert result.eta_seconds == pytest.approx(500.0 / _DEFAULT_SPEED_MS)

    def test_negative_speed_uses_default(self):
        result = compute_eta(200.0, -3.0)
        assert result.clamped is True
        assert result.speed_ms == pytest.approx(_DEFAULT_SPEED_MS)

    def test_speed_below_min_threshold_uses_default(self):
        result = compute_eta(100.0, _MIN_SPEED_MS - 0.01)
        assert result.clamped is True

    def test_speed_at_min_threshold_is_not_clamped(self):
        result = compute_eta(100.0, _MIN_SPEED_MS)
        assert result.clamped is False
        assert result.speed_ms == pytest.approx(_MIN_SPEED_MS)

    def test_zero_distance_returns_zero_eta(self):
        result = compute_eta(0.0, 10.0)
        assert result.eta_seconds == pytest.approx(0.0)

    def test_negative_distance_is_clamped_to_zero(self):
        result = compute_eta(-50.0, 10.0)
        assert result.distance_m == 0.0
        assert result.eta_seconds == pytest.approx(0.0)

    def test_result_is_immutable(self):
        result = compute_eta(100.0, 5.0)
        with pytest.raises(Exception):
            result.eta_seconds = 999.0  # type: ignore[misc]

    def test_returns_eta_result_type(self):
        result = compute_eta(300.0, 8.3)
        assert isinstance(result, EtaResult)
