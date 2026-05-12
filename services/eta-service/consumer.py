"""Kafka-to-Redis consumer for ETA feature messages.

N-1 uses this module to consume `transport-eta-features`, cache the latest
snapshot per trip in Redis, and publish live ETA updates to the `eta:live`
Pub/Sub channel.
"""

from __future__ import annotations

import json
import datetime as dt_module
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from models.eta import EtaResult, compute_eta


ETA_SNAPSHOT_KEY_PREFIX = "eta:trip"
ETA_LIVE_CHANNEL = "eta:live"
DEFAULT_SNAPSHOT_TTL_SECONDS = 300
DEFAULT_MODEL_NAME = "xgboost"

_METRICS = {
    "predictions_total": 0,
    "skipped_off_route_total": 0,
    "prediction_latency_seconds_sum": 0.0,
    "prediction_latency_seconds_count": 0,
}


def _is_off_route_payload(payload: Mapping[str, Any]) -> bool:
    if "offRoute" in payload:
        return bool(payload["offRoute"])
    if "onRoute" in payload:
        return not bool(payload["onRoute"])
    if "on_route" in payload:
        return not bool(payload["on_route"])
    return False


def _route_deviation_meters(payload: Mapping[str, Any]) -> float:
    for field in ("offRouteDistanceM", "routeDeviationMeters", "route_deviation_meters"):
        try:
            return float(payload.get(field, 0.0))
        except (TypeError, ValueError):
            continue
    return 0.0


def _is_inactive_trip_payload(payload: Mapping[str, Any]) -> bool:
    status = payload.get("trip_status", payload.get("tripStatus", "ACTIVE"))
    return str(status).upper() == "INACTIVE"


def render_prometheus_metrics() -> str:
    """Return Prometheus text exposition for ETA inference counters."""
    avg_latency = 0.0
    count = _METRICS["prediction_latency_seconds_count"]
    if count:
        avg_latency = _METRICS["prediction_latency_seconds_sum"] / count
    lines = [
        "# HELP eta_predictions_total ETA predictions published",
        "# TYPE eta_predictions_total counter",
        f"eta_predictions_total {_METRICS['predictions_total']}",
        "# HELP eta_skipped_off_route_total ETA messages skipped because bus is off-route",
        "# TYPE eta_skipped_off_route_total counter",
        f"eta_skipped_off_route_total {_METRICS['skipped_off_route_total']}",
        "# HELP eta_prediction_latency_seconds_sum Total ETA processing latency in seconds",
        "# TYPE eta_prediction_latency_seconds_sum counter",
        f"eta_prediction_latency_seconds_sum {_METRICS['prediction_latency_seconds_sum']:.9f}",
        "# HELP eta_prediction_latency_seconds_count ETA processing latency sample count",
        "# TYPE eta_prediction_latency_seconds_count counter",
        f"eta_prediction_latency_seconds_count {count}",
        "# HELP eta_prediction_latency_seconds_avg Average ETA processing latency in seconds",
        "# TYPE eta_prediction_latency_seconds_avg gauge",
        f"eta_prediction_latency_seconds_avg {avg_latency:.9f}",
    ]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class EtaFeatureMessage:
    trip_id: str
    bus_id: str
    route_id: str
    next_stop_id: int
    distance_to_next_stop: float
    stops_remaining: int
    stops_ahead: list[dict[str, Any]]
    speed_ms: float
    route_progress_pct: float
    timestamp: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "EtaFeatureMessage":
        required_fields = (
            "tripId",
            "busId",
            "routeId",
            "nextStopId",
            "distanceToNextStop",
            "stopsRemaining",
            "stopsAhead",
            "speed",
            "routeProgressPct",
            "timestamp",
        )
        missing_fields = [field for field in required_fields if field not in payload]
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"Missing ETA feature fields: {missing}")

        stops_ahead = payload["stopsAhead"]
        if not isinstance(stops_ahead, list):
            raise ValueError("stopsAhead must be a list")

        return cls(
            trip_id=str(payload["tripId"]),
            bus_id=str(payload["busId"]),
            route_id=str(payload["routeId"]),
            next_stop_id=int(payload["nextStopId"]),
            distance_to_next_stop=float(payload["distanceToNextStop"]),
            stops_remaining=int(payload["stopsRemaining"]),
            stops_ahead=[dict(stop) for stop in stops_ahead],
            speed_ms=float(payload["speed"]),
            route_progress_pct=float(payload["routeProgressPct"]),
            timestamp=str(payload["timestamp"]),
        )


class EtaFeatureConsumer:
    """Process ETA feature events and publish live snapshots.

    The consumer is intentionally dependency-injected so it can be tested
    without a running Kafka broker or Redis instance.
    """

    def __init__(
        self,
        redis_client: Any,
        *,
        kafka_broker_url: str = "broker:29092",
        topic_name: str = "transport-eta-features",
        consumer_group_id: str = "eta-service",
        default_model: str = DEFAULT_MODEL_NAME,
        snapshot_ttl_seconds: int = DEFAULT_SNAPSHOT_TTL_SECONDS,
        live_channel: str = ETA_LIVE_CHANNEL,
        snapshot_key_prefix: str = ETA_SNAPSHOT_KEY_PREFIX,
        eta_computer: Callable[[float, float], Any] = compute_eta,
        consumer_factory: Callable[..., Any] | None = None,
    ):
        self.redis_client = redis_client
        self.kafka_broker_url = kafka_broker_url
        self.topic_name = topic_name
        self.consumer_group_id = consumer_group_id
        self.default_model = default_model
        self.snapshot_ttl_seconds = snapshot_ttl_seconds
        self.live_channel = live_channel
        self.snapshot_key_prefix = snapshot_key_prefix
        self.eta_computer = eta_computer
        self.consumer_factory = consumer_factory

    def snapshot_key(self, trip_id: str) -> str:
        return f"{self.snapshot_key_prefix}:{trip_id}:snapshot"

    def decode_message(self, message: Any) -> Mapping[str, Any]:
        if isinstance(message, Mapping):
            return message

        raw_value = getattr(message, "value", message)
        if isinstance(raw_value, (bytes, bytearray)):
            raw_value = raw_value.decode("utf-8")

        if isinstance(raw_value, str):
            return json.loads(raw_value)

        raise TypeError("Unsupported ETA feature message payload")

    def build_snapshot(
        self,
        event: EtaFeatureMessage,
        eta_result: Any,
        *,
        model_used: str,
        stop_etas: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "busId": event.bus_id,
            "routeId": event.route_id,
            "speed": event.speed_ms,
            "nextStopId": event.next_stop_id,
            "distanceToNextStop": event.distance_to_next_stop,
            "stopsRemaining": event.stops_remaining,
            "stopsAhead": event.stops_ahead,
            "routeProgressPct": event.route_progress_pct,
            "timestamp": event.timestamp,
            "etaSeconds": eta_result.eta_seconds,
            "effectiveSpeedMs": eta_result.speed_ms,
            "speedClamped": eta_result.clamped,
            "modelUsed": model_used,
            "stopEtas": stop_etas or [],
        }

    def build_live_event(
        self,
        event: EtaFeatureMessage,
        eta_result: Any,
        *,
        model_used: str,
        stop_etas: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        stop_name = next(
            (
                stop.get("stopName")
                for stop in event.stops_ahead
                if int(stop.get("stopId", -1)) == event.next_stop_id
            ),
            None,
        )
        return {
            "event": "eta_update",
            "tripId": event.trip_id,
            "busId": event.bus_id,
            "routeId": event.route_id,
            "stopId": event.next_stop_id,
            "stopName": stop_name,
            "eta_seconds": eta_result.eta_seconds,
            "model_used": model_used,
            "routeProgressPct": event.route_progress_pct,
            "distanceToNextStop": event.distance_to_next_stop,
            "stop_etas": stop_etas or [],
            "timestamp": event.timestamp,
        }

    def build_stop_etas(
        self,
        event: EtaFeatureMessage,
        first_eta_result: Any,
        *,
        first_model_used: str,
        model_name: str | None = None,
    ) -> list[dict[str, Any]]:
        stop_etas = []
        for index, stop in enumerate(event.stops_ahead):
            try:
                stop_id = int(stop.get("stopId"))
            except (TypeError, ValueError):
                continue

            distance_m = float(stop.get("distanceAlongRouteMeters", event.distance_to_next_stop))
            if stop_id == event.next_stop_id:
                eta_result = first_eta_result
                model_used = first_model_used
            else:
                eta_result, model_used = self._predict_eta(
                    distance_m,
                    event.speed_ms,
                    stops_remaining=index + 1,
                    timestamp=event.timestamp,
                    model_name=model_name,
                    route_id=event.route_id,
                    stop_id=stop_id,
                )

            stop_etas.append(
                {
                    "stop_id": stop_id,
                    "stopId": stop_id,
                    "stop_name": stop.get("stopName"),
                    "stopName": stop.get("stopName"),
                    "eta_seconds": eta_result.eta_seconds,
                    "etaSeconds": eta_result.eta_seconds,
                    "distance_m": distance_m,
                    "distanceMeters": distance_m,
                    "model_used": model_used,
                    "modelUsed": model_used,
                }
            )
        return stop_etas

    def _parse_timestamp(self, timestamp: str) -> dt_module.datetime | None:
        try:
            return dt_module.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except Exception:
            return None

    def _predict_eta(
        self,
        distance_m: float,
        speed_ms: float,
        *,
        stops_remaining: int,
        timestamp: str,
        model_name: str | None = None,
        route_id: str | None = None,
        stop_id: int | None = None,
    ) -> tuple[Any, str]:
        selected_model = (model_name or self.default_model).lower().strip()
        parsed_timestamp = self._parse_timestamp(timestamp)

        if selected_model == "sarima" and route_id and stop_id is not None:
            try:
                from models.sarima_eta import forecast_eta_sarima

                sarima_seconds = forecast_eta_sarima(route_id, stop_id, parsed_timestamp)
                if sarima_seconds is not None:
                    physics = self.eta_computer(distance_m, speed_ms)
                    return (
                        EtaResult(
                            eta_seconds=float(sarima_seconds),
                            distance_m=max(0.0, distance_m),
                            speed_ms=physics.speed_ms,
                            clamped=physics.clamped,
                        ),
                        "sarima",
                    )
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "SARIMA ETA unavailable, falling back to XGBoost/physics: %s", exc
                )

        if selected_model in {"xgboost", "sarima"}:
            try:
                from models.ml_eta_xgb import predict_eta_xgb_with_fallback

                result, model_used = predict_eta_xgb_with_fallback(
                    distance_m,
                    speed_ms,
                    stops_remaining=stops_remaining,
                    dt=parsed_timestamp,
                )
                return result, model_used
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "XGBoost ETA unavailable, falling back to physics: %s", exc
                )

        result = self.eta_computer(distance_m, speed_ms)
        return result, "physics"

    def process_payload(
        self,
        payload: Mapping[str, Any],
        *,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        # Off-route guard: skip ETA computation when Flink flags the bus as off-route.
        # Supports the CR1 snake_case field and the newer offRoute additive field.
        if _is_off_route_payload(payload):
            _METRICS["skipped_off_route_total"] += 1
            logging.getLogger(__name__).warning(
                "Skipping ETA for off-route bus %s (trip %s, deviation %.1f m)",
                payload.get("busId"),
                payload.get("tripId"),
                _route_deviation_meters(payload),
            )
            return {"skipped": True, "reason": "off_route"}
        if _is_inactive_trip_payload(payload):
            logging.getLogger(__name__).warning(
                "Skipping ETA for inactive trip telemetry from bus %s (trip %s)",
                payload.get("busId"),
                payload.get("tripId"),
            )
            return {"skipped": True, "reason": "inactive_trip"}

        started = time.perf_counter()
        event = EtaFeatureMessage.from_payload(payload)
        eta_result, model_used = self._predict_eta(
            event.distance_to_next_stop,
            event.speed_ms,
            stops_remaining=event.stops_remaining,
            timestamp=event.timestamp,
            model_name=model_name,
            route_id=event.route_id,
            stop_id=event.next_stop_id,
        )

        stop_etas = self.build_stop_etas(
            event,
            eta_result,
            first_model_used=model_used,
            model_name=model_name,
        )
        snapshot_payload = self.build_snapshot(
            event,
            eta_result,
            model_used=model_used,
            stop_etas=stop_etas,
        )
        live_event = self.build_live_event(
            event,
            eta_result,
            model_used=model_used,
            stop_etas=stop_etas,
        )

        snapshot_json = json.dumps(snapshot_payload, separators=(",", ":"), sort_keys=True)
        live_event_json = json.dumps(live_event, separators=(",", ":"), sort_keys=True)

        self.redis_client.setex(
            self.snapshot_key(event.trip_id),
            self.snapshot_ttl_seconds,
            snapshot_json,
        )
        self.redis_client.publish(self.live_channel, live_event_json)
        elapsed = time.perf_counter() - started
        _METRICS["predictions_total"] += 1
        _METRICS["prediction_latency_seconds_sum"] += elapsed
        _METRICS["prediction_latency_seconds_count"] += 1

        # Persist ETA observation to eta_db for SARIMA training data.
        # Non-blocking best-effort: any failure is logged but never raised
        # so a DB outage cannot disrupt the real-time ETA pipeline.
        try:
            from models import eta_db

            eta_db.insert_record(
                snapshot_payload,
                stop_id=event.next_stop_id,
                off_route=False,
            )
        except Exception as _db_exc:
            logging.getLogger(__name__).error(
                "eta_db insert failed (non-fatal): %s", _db_exc
            )

        return {
            "snapshot_key": self.snapshot_key(event.trip_id),
            "snapshot": snapshot_payload,
            "live_event": live_event,
            "eta_result": eta_result,
            "model_used": model_used,
        }

    def process_message(self, message: Any) -> dict[str, Any]:
        payload = self.decode_message(message)
        return self.process_payload(payload)

    def create_kafka_consumer(self):
        if self.consumer_factory is not None:
            return self.consumer_factory(
                bootstrap_servers=self.kafka_broker_url,
                group_id=self.consumer_group_id,
                topic_name=self.topic_name,
            )

        try:
            from kafka import KafkaConsumer
        except ImportError as exc:  # pragma: no cover - runtime dependency guard
            raise RuntimeError(
                "kafka-python is required to run the ETA Kafka consumer"
            ) from exc

        return KafkaConsumer(
            self.topic_name,
            bootstrap_servers=self.kafka_broker_url,
            group_id=self.consumer_group_id,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda value: value.decode("utf-8"),
        )

    def consume_forever(self, stop_event: threading.Event | None = None) -> None:
        consumer = self.create_kafka_consumer()
        try:
            for message in consumer:
                if stop_event is not None and stop_event.is_set():
                    break
                self.process_message(message)
        finally:
            close = getattr(consumer, "close", None)
            if callable(close):
                close()

