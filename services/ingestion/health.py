# services/ingestion/health.py
# Health and metrics endpoints for the Ingestion Service.
# Runs on port 8001 via FastAPI + Uvicorn.

from datetime import datetime, timezone

from fastapi import FastAPI

from services.ingestion.metrics import metrics
from services.ingestion.config import settings


def create_app():
    """Create the FastAPI app."""
    app = FastAPI(
        title="OnTime Ingestion Service",
        version="1.0.0",
        description="Health and metrics endpoints for the GPS ingestion service"
    )

    @app.get("/health")
    def health():
        """
        Health check endpoint.
        Returns service status, dependencies, and message counters.
        """
        snapshot = metrics.get_snapshot()

        # Determine overall status
        kafka_ok = snapshot["kafka_broker_up"]
        mqtt_ok = snapshot["mqtt_broker_up"]
        status = "healthy" if (kafka_ok and mqtt_ok) else "degraded"

        return {
            "status": status,
            "service": "ingestion-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": {
                "kafka_broker": "up" if kafka_ok else "down",
                "mqtt_broker": "up" if mqtt_ok else "down",
            },
            "counters": {
                "messages_received": snapshot["messages_received"],
                "messages_validated": snapshot["messages_validated"],
                "messages_rejected": snapshot["messages_rejected"],
            },
        }

    @app.get("/metrics")
    def metrics_endpoint():
        """
        Prometheus-format metrics endpoint.
        """
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
            f'ingestion_messages_rejected_total{{reason="SCHEMA_VALIDATION"}} {snapshot["messages_rejected_schema"]}',
            f'ingestion_messages_rejected_total{{reason="GEO_BOUNDS"}} {snapshot["messages_rejected_geo"]}',
            f'ingestion_messages_rejected_total{{reason="DUPLICATE"}} {snapshot["messages_rejected_duplicate"]}',
            f'ingestion_messages_rejected_total{{reason="RATE_LIMIT"}} {snapshot["messages_rejected_rate_limit"]}',
            f'ingestion_messages_rejected_total{{reason="SEQUENCE_ERROR"}} {snapshot["messages_rejected_sequence"]}',
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
    """
    Start the FastAPI health server in a blocking manner.
    Call this from a daemon thread in main.py.
    """
    import uvicorn
    import logging

    # Suppress uvicorn logs (optional - comment out if you want them)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.service_port,
        log_level="info",
    )
