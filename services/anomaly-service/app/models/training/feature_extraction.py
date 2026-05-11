"""Feature extraction helpers for anomaly-service training.

These helpers convert a sliding window of telemetry dicts into a single
summary vector suitable for an unsupervised detector such as Isolation Forest.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean, pvariance
from typing import Any, Dict, Iterable, List


def _parse_timestamp(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        current = value
    elif isinstance(value, str):
        candidate = value.replace("Z", "+00:00")
        try:
            current = datetime.fromisoformat(candidate)
        except ValueError:
            return None
    else:
        return None

    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).timestamp()


def build_summary_vector(window: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """Reduce a telemetry window into stable numeric features.

    The detector expects one feature vector per window, not raw coordinates.
    """
    entries: List[Dict[str, Any]] = list(window)
    if len(entries) < 2:
        return {
            "max_acceleration": 0.0,
            "min_acceleration": 0.0,
            "speed_variance": 0.0,
            "heading_variance": 0.0,
            "average_speed": 0.0,
            "sample_count": float(len(entries)),
        }

    speeds: List[float] = []
    headings: List[float] = []
    accelerations: List[float] = []
    previous_timestamp: float | None = None
    previous_speed: float | None = None

    for entry in entries:
        timestamp = _parse_timestamp(entry.get("timestamp"))
        if timestamp is None:
            continue

        speed = entry.get("speed")
        if speed is None:
            speed = entry.get("speed_ms", 0.0)
        heading = entry.get("heading", 0.0)

        speed_value = float(speed)
        heading_value = float(heading)
        speeds.append(speed_value)
        headings.append(heading_value)

        if previous_timestamp is not None and previous_speed is not None:
            delta_seconds = timestamp - previous_timestamp
            if delta_seconds > 0:
                accelerations.append((speed_value - previous_speed) / delta_seconds)

        previous_timestamp = timestamp
        previous_speed = speed_value

    return {
        "max_acceleration": max(accelerations) if accelerations else 0.0,
        "min_acceleration": min(accelerations) if accelerations else 0.0,
        "speed_variance": pvariance(speeds) if len(speeds) > 1 else 0.0,
        "heading_variance": pvariance(headings) if len(headings) > 1 else 0.0,
        "average_speed": mean(speeds) if speeds else 0.0,
        "sample_count": float(len(speeds)),
    }
