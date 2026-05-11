# services/eta-service/models/eta.py
# Physics heuristic ETA model — distance ÷ speed.
# Inc 1: pure physics formula.  Inc 2: XGBoost predictor replaces this.

from dataclasses import dataclass

_DEFAULT_SPEED_MS: float = 5.0   # 18 km/h urban fallback (used when speed unavailable)
_MIN_SPEED_MS: float = 1.4       # ~5 km/h — minimum credible moving speed (plan K-5)


@dataclass(frozen=True)
class EtaResult:
    eta_seconds: float          # estimated seconds until arrival
    distance_m: float           # remaining distance passed in
    speed_ms: float             # effective speed used in computation
    clamped: bool               # True if speed was below minimum and clamped


def compute_eta(remaining_distance_m: float, speed_ms: float) -> EtaResult:
    """Return an EtaResult for a bus given remaining distance and current speed.

    Formula: eta_seconds = remaining_distance_m / max(speed_ms, _MIN_SPEED_MS)

    Args:
        remaining_distance_m: Metres from bus to target stop (must be >= 0).
        speed_ms: Current bus speed in m/s.  Values below _MIN_SPEED_MS are
                  clamped to _MIN_SPEED_MS (bus moving slowly or GPS noise).

    Returns:
        EtaResult with eta_seconds >= 0.
    """
    if remaining_distance_m < 0:
        remaining_distance_m = 0.0

    clamped = False
    effective_speed = speed_ms
    if effective_speed < _MIN_SPEED_MS:
        effective_speed = _MIN_SPEED_MS
        clamped = True

    eta_seconds = remaining_distance_m / effective_speed

    return EtaResult(
        eta_seconds=eta_seconds,
        distance_m=remaining_distance_m,
        speed_ms=effective_speed,
        clamped=clamped,
    )
