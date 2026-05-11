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
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from models.eta import compute_eta


ETA_SNAPSHOT_KEY_PREFIX = "eta:trip"
ETA_LIVE_CHANNEL = "eta:live"
DEFAULT_SNAPSHOT_TTL_SECONDS = 300
DEFAULT_MODEL_NAME = "xgboost"


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
        }

    def build_live_event(
        self,
        event: EtaFeatureMessage,
        eta_result: Any,
        *,
        model_used: str,
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
            "timestamp": event.timestamp,
        }

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
    ) -> tuple[Any, str]:
        selected_model = (model_name or self.default_model).lower().strip()
        if selected_model == "xgboost":
            try:
                from models.ml_eta_xgb import predict_eta_xgb

                result = predict_eta_xgb(
                    distance_m,
                    speed_ms,
                    stops_remaining=stops_remaining,
                    dt=self._parse_timestamp(timestamp),
                )
                return result, "xgboost"
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
        # Off-route guard: skip ETA computation when Flink flags the bus as
        # off-route.  Defaults to True (on-route) for backward compatibility
        # with messages from non-Flink sources that omit the field.
        if not payload.get("onRoute", True):
            logging.getLogger(__name__).warning(
                "Skipping ETA for off-route bus %s (trip %s, deviation %.1f m)",
                payload.get("busId"),
                payload.get("tripId"),
                payload.get("routeDeviationMeters", 0.0),
            )
            return {"skipped": True, "reason": "off_route"}

        event = EtaFeatureMessage.from_payload(payload)
        eta_result, model_used = self._predict_eta(
            event.distance_to_next_stop,
            event.speed_ms,
            stops_remaining=event.stops_remaining,
            timestamp=event.timestamp,
            model_name=model_name,
        )

        snapshot_payload = self.build_snapshot(event, eta_result, model_used=model_used)
        live_event = self.build_live_event(event, eta_result, model_used=model_used)

        snapshot_json = json.dumps(snapshot_payload, separators=(",", ":"), sort_keys=True)
        live_event_json = json.dumps(live_event, separators=(",", ":"), sort_keys=True)

        self.redis_client.setex(
            self.snapshot_key(event.trip_id),
            self.snapshot_ttl_seconds,
            snapshot_json,
        )
        self.redis_client.publish(self.live_channel, live_event_json)

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
            auto_offset_reset="latest",
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

