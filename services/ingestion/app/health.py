from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, PlainTextResponse

from services.ingestion.app.config import settings
from services.ingestion.app.metrics import metrics


def _build_health_payload(snapshot: dict) -> dict:
    kafka_ok = snapshot["kafka_broker_up"]
    mqtt_ok = snapshot["mqtt_broker_up"]

    return {
        "status": "healthy" if (kafka_ok and mqtt_ok) else "degraded",
        "service": "ingestion-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "kafka_broker": "up" if kafka_ok else "down",
            "mqtt_broker": "up" if mqtt_ok else "down",
            "trip_cache": snapshot["trip_cache_status"],
        },
        "counters": {
            "messages_received": snapshot["messages_received"],
            "messages_validated": snapshot["messages_validated"],
            "messages_rejected": snapshot["messages_rejected"],
            "active_trip_count": snapshot["active_trip_count"],
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
            if snapshot["kafka_broker_up"] and snapshot["mqtt_broker_up"]
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
            "# HELP ingestion_messages_rejected_total Total messages rejected by error type",
            "# TYPE ingestion_messages_rejected_total counter",
            f'ingestion_messages_rejected_total{{reason="JSON_PARSE"}} {snapshot["messages_rejected_json"]}',
            f'ingestion_messages_rejected_total{{reason="MISSING_TIMESTAMP"}} {snapshot["messages_rejected_missing_timestamp"]}',
            f'ingestion_messages_rejected_total{{reason="SCHEMA_VALIDATION"}} {snapshot["messages_rejected_schema"]}',
            f'ingestion_messages_rejected_total{{reason="GEO_BOUNDS"}} {snapshot["messages_rejected_geo"]}',
            f'ingestion_messages_rejected_total{{reason="DUPLICATE"}} {snapshot["messages_rejected_duplicate"]}',
            f'ingestion_messages_rejected_total{{reason="INACTIVE_TRIP"}} {snapshot["messages_rejected_inactive_trip"]}',
            f'ingestion_messages_rejected_total{{reason="TRIP_CACHE_REBUILDING"}} {snapshot["messages_rejected_trip_cache_rebuilding"]}',
            f'ingestion_messages_rejected_total{{reason="RATE_LIMIT"}} {snapshot["messages_rejected_rate_limit"]}',
            f'ingestion_messages_rejected_total{{reason="RATE_LIMIT_EVENT_TIME"}} {snapshot["messages_rejected_rate_limit_event_time"]}',
            f'ingestion_messages_rejected_total{{reason="SEQUENCE_ERROR"}} {snapshot["messages_rejected_sequence"]}',
            f'ingestion_messages_rejected_total{{reason="FUTURE_TIMESTAMP"}} {snapshot["messages_rejected_future_timestamp"]}',
            f'ingestion_messages_rejected_total{{reason="STALE_REPLAY"}} {snapshot["messages_rejected_stale_replay"]}',
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
