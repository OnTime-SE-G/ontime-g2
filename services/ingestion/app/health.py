from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, PlainTextResponse

from services.ingestion.app.config import settings
from services.ingestion.app.metrics import REJECTION_REASONS, metrics


def _trip_cache_ready(snapshot: dict) -> bool:
    if settings.stateless_mode:
        return True
    if not settings.require_active_trip:
        return True
    return snapshot["trip_cache_status"] == "ready"


def _dependencies_ready(snapshot: dict) -> bool:
    return (
        snapshot["kafka_broker_up"]
        and snapshot["mqtt_broker_up"]
        and _trip_cache_ready(snapshot)
    )


def _build_health_payload(snapshot: dict) -> dict:
    kafka_ok = snapshot["kafka_broker_up"]
    mqtt_ok = snapshot["mqtt_broker_up"]
    dependencies_ok = _dependencies_ready(snapshot)

    return {
        "status": "healthy" if dependencies_ok else "degraded",
        "service": "ingestion-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "kafka_broker": "up" if kafka_ok else "down",
            "mqtt_broker": "up" if mqtt_ok else "down",
            "trip_cache": snapshot["trip_cache_status"],
        },
        "trip_cache": {
            "ready": _trip_cache_ready(snapshot),
            "status": snapshot["trip_cache_status"],
            "active_trip_count": snapshot["active_trip_count"],
            "last_lifecycle_event_timestamp": snapshot["last_trip_lifecycle_time"],
        },
        "counters": {
            "messages_received": snapshot["messages_received"],
            "messages_validated": snapshot["messages_validated"],
            "heartbeats_received": snapshot["heartbeat_messages_received"],
            "heartbeats_invalid": snapshot["heartbeat_messages_invalid"],
            "messages_rejected": snapshot["messages_rejected"],
            "active_trip_count": snapshot["active_trip_count"],
        },
        "device_status": {
            "latest_heartbeat_by_bus": snapshot["latest_heartbeat_by_bus"],
        },
    }


def create_app():
    app = FastAPI(
        title="OnTime Ingestion Service",
        version="1.1.0",
        description="Health and metrics endpoints for the GPS ingestion service",
    )

    @app.get("/health")
    def health():
        return _build_health_payload(metrics.get_snapshot())

    @app.get("/health/live")
    def live():
        return {
            "status": "alive",
            "service": "ingestion-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/health/ready")
    def ready():
        snapshot = metrics.get_snapshot()
        payload = _build_health_payload(snapshot)
        status_code = (
            status.HTTP_200_OK
            if _dependencies_ready(snapshot)
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return JSONResponse(status_code=status_code, content=payload)

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics_endpoint():
        snapshot = metrics.get_snapshot()
        prometheus_lines = [
            "# HELP ingestion_messages_received_total Total messages received from MQTT",
            "# TYPE ingestion_messages_received_total counter",
            f'ingestion_messages_received_total {snapshot["messages_received"]}',
            "",
            "# HELP ingestion_messages_validated_total Total messages validated and sent to Kafka",
            "# TYPE ingestion_messages_validated_total counter",
            f'ingestion_messages_validated_total {snapshot["messages_validated"]}',
            "",
            "# HELP ingestion_heartbeat_messages_received_total Total heartbeat messages received from MQTT",
            "# TYPE ingestion_heartbeat_messages_received_total counter",
            (
                "ingestion_heartbeat_messages_received_total "
                f'{snapshot["heartbeat_messages_received"]}'
            ),
            "",
            "# HELP ingestion_heartbeat_messages_invalid_total Total invalid heartbeat messages received from MQTT",
            "# TYPE ingestion_heartbeat_messages_invalid_total counter",
            f'ingestion_heartbeat_messages_invalid_total {snapshot["heartbeat_messages_invalid"]}',
            "",
            "# HELP ingestion_heartbeat_age_seconds Last heartbeat age per bus",
            "# TYPE ingestion_heartbeat_age_seconds gauge",
            *[
                f'ingestion_heartbeat_age_seconds{{bus_id="{bus_id}"}} {age_seconds:.1f}'
                for bus_id, age_seconds in snapshot["heartbeat_age_seconds_by_bus"].items()
            ],
            "",
            "# HELP ingestion_messages_rejected_total Total messages rejected by error type",
            "# TYPE ingestion_messages_rejected_total counter",
            *[
                (
                    f'ingestion_messages_rejected_total{{reason="{reason}"}} '
                    f'{snapshot["rejections_by_reason"][reason]}'
                )
                for reason in REJECTION_REASONS
            ],
            "",
            "# HELP ingestion_trip_cache_ready Active trip cache readiness (1=ready, 0=not ready)",
            "# TYPE ingestion_trip_cache_ready gauge",
            f'ingestion_trip_cache_ready {1 if _trip_cache_ready(snapshot) else 0}',
            "",
            "# HELP ingestion_trip_cache_active_trips Active trips currently cached",
            "# TYPE ingestion_trip_cache_active_trips gauge",
            f'ingestion_trip_cache_active_trips {snapshot["active_trip_count"]}',
            "",
            "# HELP ingestion_uptime_seconds Service uptime in seconds",
            "# TYPE ingestion_uptime_seconds gauge",
            f'ingestion_uptime_seconds {snapshot["uptime_seconds"]:.1f}',
            "",
            "# HELP ingestion_kafka_broker_up Kafka broker connectivity status (1=up, 0=down)",
            "# TYPE ingestion_kafka_broker_up gauge",
            f'ingestion_kafka_broker_up {1 if snapshot["kafka_broker_up"] else 0}',
            "",
            "# HELP ingestion_mqtt_broker_up MQTT broker connectivity status (1=up, 0=down)",
            "# TYPE ingestion_mqtt_broker_up gauge",
            f'ingestion_mqtt_broker_up {1 if snapshot["mqtt_broker_up"] else 0}',
        ]
        return "\n".join(prometheus_lines)

    return app


app = create_app()


def start_health_server():
    import logging

    import uvicorn

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.service_port,
        log_level="info",
    )
