# services/ingestion/main.py
# Ingestion Service entry point.
# Subscribes to MQTT, validates GPS messages, and produces to Kafka.

import signal
import sys

from config import settings


def handle_shutdown(sig, frame):
    """Graceful shutdown handler for SIGINT/SIGTERM."""
    print("\nShutting down Ingestion Service...")
    sys.exit(0)


def main():
    """Start the Ingestion Service."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("=" * 50)
    print("  OnTime Ingestion Service")
    print("=" * 50)
    print(f"  MQTT Broker:  {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
    print(f"  MQTT Topic:   {settings.mqtt_topic_pattern}")
    print(f"  Kafka Broker: {settings.kafka_broker_url}")
    print(f"  Raw Topic:    {settings.kafka_raw_topic}")
    print(f"  DLQ Topic:    {settings.kafka_dlq_topic}")
    print(f"  Health Port:  {settings.service_port}")
    print("=" * 50)

    # TODO (Phase 2): Initialize Kafka producer
    # TODO (Phase 3): Initialize validation engine
    # TODO (Phase 4): Initialize MQTT subscriber and start loop
    # TODO (Phase 6): Start FastAPI health server in background thread

    print("Service scaffolding loaded. Components will be wired in Phase 2-6.")


if __name__ == "__main__":
    main()
