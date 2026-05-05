import signal
import sys
import threading

from services.ingestion.app.config import settings
from services.ingestion.app.health import start_health_server
from services.ingestion.app.metrics import metrics
from services.ingestion.app.mqtt_subscriber import MQTTSubscriber
from services.ingestion.app.producer import TelemetryProducer
from services.ingestion.app.trip_lifecycle_cache import ActiveTripCache, TripLifecycleConsumer

producer = None
subscriber = None
trip_cache = None
trip_consumer = None
health_thread = None


def handle_shutdown(sig, frame):
    print("\nShutting down Ingestion Service...")
    if subscriber:
        print("Stopping MQTT subscriber...")
        subscriber.stop()
    if trip_consumer:
        print("Stopping trip lifecycle consumer...")
        trip_consumer.stop()
    if producer:
        print("Closing Kafka producer...")
        producer.close()
    print("Ingestion Service shut down successfully.")
    sys.exit(0)


def main():
    global producer, subscriber, trip_cache, trip_consumer, health_thread

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
    print(f"  Trip Topic:   {settings.kafka_trip_lifecycle_topic}")
    print(f"  Health Port:  {settings.service_port}")
    print("=" * 50)

    print("Initializing Kafka producer...")
    try:
        producer = TelemetryProducer()
        metrics.kafka_broker_up = True
        print("Kafka producer initialized successfully.")
    except Exception as error:
        metrics.kafka_broker_up = False
        print(f"Failed to initialize Kafka producer: {error}")

    print("Initializing MQTT subscriber...")
    if producer is not None:
        try:
            trip_cache = ActiveTripCache(initial_status="rebuilding")
            trip_consumer = TripLifecycleConsumer(trip_cache)
            trip_consumer.start()
            subscriber = MQTTSubscriber(producer, trip_cache=trip_cache)
            subscriber.connect()
            print("MQTT subscriber initialized.")
        except Exception as error:
            metrics.mqtt_broker_up = False
            print(f"Failed to connect MQTT subscriber: {error}")
    else:
        metrics.mqtt_broker_up = False
        print("Skipping MQTT subscriber startup because Kafka producer is unavailable.")

    print(f"Starting health/metrics server on port {settings.service_port}...")
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    print("Health server started (daemon thread).")

    if subscriber:
        print("All components loaded. Starting MQTT loop.")
        subscriber.start()
    else:
        print("Running in degraded mode. Waiting for shutdown while health endpoints remain available.")
        threading.Event().wait()


if __name__ == "__main__":  # pragma: no cover
    main()
