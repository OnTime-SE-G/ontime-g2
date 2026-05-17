"""Feature contracts shared by training and inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ETA_XGB_FEATURES = [
    "distance_m",
    "speed_ms",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "stops_remaining",
    "physics_eta",
]

ETA_XGB_URBAN_FEATURES = ETA_XGB_FEATURES + ["segment_mode_urban"]

ANOMALY_IF_BEHAVIORAL_FEATURES = [
    "max_acceleration",
    "min_acceleration",
    "speed_variance",
    "heading_variance",
    "average_speed",
    "sample_count",
]

ANOMALY_IF_SPATIAL_FEATURES = [
    "route_deviation_meters",
    "speed_kmh",
    "stationary_duration_sec",
    "distance_to_next_stop_m",
    "route_progress_pct",
]


@dataclass(frozen=True)
class ModelContract:
    name: str
    version: str
    features: list[str]
    target: str | None = None
    tags: dict[str, str] | None = None


MODEL_CONTRACTS: dict[str, ModelContract] = {
    "ontime-eta-xgb": ModelContract(
        name="ontime-eta-xgb",
        version="eta_xgb_v1",
        features=ETA_XGB_FEATURES,
        target="eta_seconds",
        tags={"model_family": "eta", "segment": "all"},
    ),
    "ontime-eta-xgb-urban": ModelContract(
        name="ontime-eta-xgb-urban",
        version="eta_xgb_urban_v1",
        features=ETA_XGB_FEATURES,
        target="eta_seconds",
        tags={"model_family": "eta", "segment": "urban"},
    ),
    "ontime-eta-xgb-expressway": ModelContract(
        name="ontime-eta-xgb-expressway",
        version="eta_xgb_expressway_v1",
        features=ETA_XGB_FEATURES,
        target="eta_seconds",
        tags={"model_family": "eta", "segment": "expressway"},
    ),
    "ontime-anomaly-if-behavioral": ModelContract(
        name="ontime-anomaly-if-behavioral",
        version="anomaly_if_behavioral_v1",
        features=ANOMALY_IF_BEHAVIORAL_FEATURES,
        tags={"model_family": "anomaly"},
    ),
    "ontime-anomaly-if-spatial": ModelContract(
        name="ontime-anomaly-if-spatial",
        version="anomaly_if_spatial_v1",
        features=ANOMALY_IF_SPATIAL_FEATURES,
        tags={"model_family": "anomaly"},
    ),
    "ontime-eta-sarima": ModelContract(
        name="ontime-eta-sarima",
        version="eta_sarima_v1",
        features=[],
        target="eta_seconds",
        tags={"model_family": "eta", "algorithm": "sarima"},
    ),
}


def build_feature_row(features: list[str], values: dict[str, Any]) -> list[float]:
    return [float(values.get(name, 0.0)) for name in features]
