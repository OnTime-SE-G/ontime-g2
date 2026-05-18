"""
Unit tests for the physics ETA model (services/eta-service/models/eta.py).
Covers K-5 / N-5: formula distance / max(speed, 1.4 m/s).
"""
import pytest
from app.prediction.eta import compute_eta, EtaResult, _MIN_SPEED_MS, _DEFAULT_SPEED_MS


class TestComputeEtaNormalCases:
    def test_normal_case(self):
        result = compute_eta(1000.0, 10.0)
        assert result.eta_seconds == pytest.approx(100.0)
        assert result.clamped is False
        print(f"\n>>> Normal: 1000m @ 10m/s = {result.eta_seconds:.1f}s")

    def test_zero_distance(self):
        result = compute_eta(0.0, 10.0)
        assert result.eta_seconds == pytest.approx(0.0)
        assert result.clamped is False
        print(f"\n>>> Zero distance: ETA = {result.eta_seconds}s")

    def test_negative_distance_treated_as_zero(self):
        result = compute_eta(-500.0, 10.0)
        assert result.eta_seconds == pytest.approx(0.0)
        assert result.distance_m == pytest.approx(0.0)
        print(f"\n>>> Negative distance clamped to 0: ETA = {result.eta_seconds}s")

    def test_large_distance(self):
        result = compute_eta(50000.0, 13.9)  # 50 km at ~50 km/h
        assert result.eta_seconds == pytest.approx(50000.0 / 13.9, rel=0.01)
        print(f"\n>>> 50km @ 13.9m/s = {result.eta_seconds:.0f}s (~{result.eta_seconds/60:.1f}min)")


class TestMinSpeedClamping:
    def test_zero_speed_clamped_to_min(self):
        result = compute_eta(1000.0, 0.0)
        assert result.clamped is True
        assert result.speed_ms == pytest.approx(_MIN_SPEED_MS)
        assert result.eta_seconds == pytest.approx(1000.0 / _MIN_SPEED_MS)
        print(f"\n>>> Zero speed clamped: ETA = {result.eta_seconds:.1f}s at {_MIN_SPEED_MS}m/s")

    def test_below_min_speed_clamped(self):
        result = compute_eta(500.0, 0.5)
        assert result.clamped is True
        assert result.speed_ms == pytest.approx(_MIN_SPEED_MS)
        print(f"\n>>> Speed 0.5 < {_MIN_SPEED_MS} → clamped to {result.speed_ms}")

    def test_exactly_min_speed_not_clamped(self):
        result = compute_eta(500.0, _MIN_SPEED_MS)
        assert result.clamped is False
        assert result.speed_ms == pytest.approx(_MIN_SPEED_MS)
        print(f"\n>>> Speed == _MIN_SPEED_MS ({_MIN_SPEED_MS}) → not clamped")

    def test_above_min_speed_not_clamped(self):
        result = compute_eta(500.0, 5.0)
        assert result.clamped is False
        assert result.speed_ms == pytest.approx(5.0)
        print(f"\n>>> Speed 5.0 > {_MIN_SPEED_MS} → not clamped")

    def test_min_speed_is_1_4(self):
        """Contract: minimum speed must be 1.4 m/s as agreed in ETA plan K-5."""
        assert _MIN_SPEED_MS == pytest.approx(1.4)
        print(f"\n>>> _MIN_SPEED_MS = {_MIN_SPEED_MS} ✓")


class TestEtaResultFields:
    def test_result_is_dataclass(self):
        result = compute_eta(200.0, 2.0)
        assert isinstance(result, EtaResult)

    def test_distance_m_reflects_input(self):
        result = compute_eta(350.0, 5.0)
        assert result.distance_m == pytest.approx(350.0)

    def test_speed_ms_reflects_effective_speed(self):
        result = compute_eta(200.0, 8.0)
        assert result.speed_ms == pytest.approx(8.0)

    def test_eta_nonnegative(self):
        for dist in [0.0, 1.0, 1000.0]:
            result = compute_eta(dist, 3.0)
            assert result.eta_seconds >= 0.0
