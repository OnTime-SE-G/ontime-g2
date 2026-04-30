# services/ingestion/main.py
# Ingestion Service entry point.
# Subscribes to MQTT, validates GPS messages, and produces to Kafka.

import signal
import sys
import threading

from services.ingestion.config import settings
from services.ingestion.producer import TelemetryProducer
from services.ingestion.mqtt_subscriber import MQTTSubscriber
from services.ingestion.health import start_health_server
from services.ingestion.metrics import metrics

producer = None
subscriber = None
health_thread = None


def handle_shutdown(sig, frame):
    """Graceful shutdown handler for SIGINT/SIGTERM."""
    print("\nShutting down Ingestion Service...")
    if subscriber:
        print("Stopping MQTT subscriber...")
        subscriber.stop()
    if producer:
        print("Closing Kafka producer...")
        producer.close()
    print("Ingestion Service shut down successfully.")
    sys.exit(0)


def main():
    """Start the Ingestion Service."""
    global producer, subscriber, health_thread
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

    # Initialize Kafka producer
    print("Initializing Kafka producer...")
    try:
        producer = TelemetryProducer()
        print("Kafka producer initialized successfully.")
        metrics.kafka_broker_up = True
    except Exception as e:
        print(f"Failed to initialize Kafka producer: {e}")
        metrics.kafka_broker_up = False

    # Validation engine (Phase 3) is a pure function and requires no initialization

    # Initialize MQTT subscriber and start loop
    print("Initializing MQTT subscriber...")
    try:
        subscriber = MQTTSubscriber(producer)
        subscriber.connect()
        print("MQTT subscriber initialized.")
        metrics.mqtt_broker_up = True
    except Exception as e:
        print(f"Failed to connect MQTT subscriber: {e}")
        metrics.mqtt_broker_up = False

    # (Phase 6): Start FastAPI health server in background daemon thread
    print("Starting health/metrics server on port 8001...")
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    print("Health server started (daemon thread).")

    print("All components loaded. Starting main loop.")

    if subscriber:
        # Start the blocking MQTT loop (runs in main thread)
        subscriber.start()
    else:
        # Block so the container doesn't exit immediately if run without subscriber
        while True:
            signal.pause()


if __name__ == "__main__":
    main()
