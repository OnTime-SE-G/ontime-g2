# services/ingestion/main.py
# Ingestion Service entry point.
# Subscribes to MQTT, validates GPS messages, and produces to Kafka.

import signal
import sys

from config import settings
from producer import TelemetryProducer
from mqtt_subscriber import MQTTSubscriber

producer = None
subscriber = None


def handle_shutdown(sig, frame):
    """Graceful shutdown handler for SIGINT/SIGTERM."""
    print("\nShutting down Ingestion Service...")
    if subscriber:
        print("Stopping MQTT subscriber...")
        subscriber.stop()
    if producer:
        print("Closing Kafka producer...")
        producer.close()
    sys.exit(0)


def main():
    """Start the Ingestion Service."""
    global producer, subscriber
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
    except Exception as e:
        print(f"Failed to initialize Kafka producer: {e}")

    # Validation engine (Phase 3) is a pure function and requires no initialization

    # Initialize MQTT subscriber and start loop
    print("Initializing MQTT subscriber...")
    try:
        subscriber = MQTTSubscriber(producer)
        subscriber.connect()
        print("MQTT subscriber initialized.")
    except Exception as e:
        print(f"Failed to connect MQTT subscriber: {e}")

    # TODO (Phase 6): Start FastAPI health server in background thread

    print("Service Phase 4 components loaded. Starting main loop.")
    
    if subscriber:
        # Start the blocking MQTT loop
        subscriber.start()
    else:
        # Block so the container doesn't exit immediately if run without subscriber
        while True:
            signal.pause()


if __name__ == "__main__":
    main()
