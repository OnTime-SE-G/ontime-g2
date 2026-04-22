import json
import random
import time
from datetime import datetime, timezone

from scripts.models.settings import settings

try:
    from kafka import KafkaProducer
except ImportError as exc:
    raise RuntimeError(
        "kafka-python is required for gps_simulator.py. Install it with 'pip install kafka-python'."
    ) from exc


def _build_position(index: int) -> tuple[float, float]:
    # Simple deterministic path with tiny jitter for repeatable local simulations.
    base_lat = 6.7900 + (index % 50) * 0.0008
    base_lng = 79.8900 + (index % 50) * 0.0008
    lat = base_lat + random.uniform(-0.0002, 0.0002)
    lng = base_lng + random.uniform(-0.0002, 0.0002)
    return lat, lng


def _build_payload(index: int) -> dict:
    lat, lng = _build_position(index)
    return {
        "busId": settings.bus_id,
        "tripId": settings.trip_id,
        "routeId": settings.route_name,
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "speed": round(random.uniform(10, 55), 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
        acks="all",
    )


def run() -> None:
    producer = create_producer()
    print(
        f"Publishing GPS messages to topic '{settings.telemetry_topic}' on '{settings.kafka_bootstrap_servers}'"
    )

    index = 0
    while True:
        payload = _build_payload(index)
        producer.send(
            settings.telemetry_topic,
            key=settings.bus_id,
            value=payload,
        )
        producer.flush()
        print(f"Published GPS event: {payload}")

        index += 1
        interval = random.randint(
            settings.min_interval_seconds, settings.max_interval_seconds)
        time.sleep(interval)


def main() -> None:
    try:
        run()
    except KeyboardInterrupt:
        print("GPS simulator stopped.")


if __name__ == "__main__":
    main()
