# services/ingestion/main.py
# Ingestion Service entry point.
# Subscribes to MQTT, validates GPS messages, and produces to Kafka.

import signal
import sys

from config import settings
from producer import TelemetryProducer

producer = None

def handle_shutdown(sig, frame):
    """Graceful shutdown handler for SIGINT/SIGTERM."""
    print("\nShutting down Ingestion Service...")
    if producer:
        print("Closing Kafka producer...")
        producer.close()
    sys.exit(0)


def main():
    """Start the Ingestion Service."""
    global producer
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
        # Not exiting yet because Kafka might not be up, or we might want it to retry (KafkaProducer handles this async usually)

    # TODO (Phase 3): Initialize validation engine
    # TODO (Phase 4): Initialize MQTT subscriber and start loop
    # TODO (Phase 6): Start FastAPI health server in background thread

    print("Service Phase 2 components loaded. Waiting for Phase 3-6 to start main loop.")
    
    # Block so the container doesn't exit immediately if run
    # In Phase 4 this will be replaced by the MQTT loop
    while True:
        signal.pause()


if __name__ == "__main__":
    main()
