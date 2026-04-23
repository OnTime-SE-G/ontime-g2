# scripts/gps_simulator.py

import json
import math
import random
import signal
import time
from typing import List, Tuple

from kafka import KafkaProducer
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from scripts.models.settings import settings
from scripts.models.db_route import RouteORM


running = True


def handle_shutdown(sig, frame):
    global running
    running = False
    print("\nStopping GPS simulator...")


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def get_engine():
    return create_engine(settings.database_url, echo=False)


def get_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )


def load_route_points() -> List[Tuple[float, float]]:
    engine = get_engine()

    with Session(engine) as session:
        route = (
            session.query(RouteORM)
            .filter(RouteORM.name == settings.route_name)
            .first()
        )

        if route is None:
            raise ValueError(
                f"Route '{settings.route_name}' not found"
            )

        line = to_shape(route.geometry)

        return [
            (float(coord[0]), float(coord[1]))
            for coord in line.coords
        ]


def haversine_km(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float
) -> float:
    earth_radius_km = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return earth_radius_km * c


def create_message(
    prev_lon: float,
    prev_lat: float,
    lon: float,
    lat: float,
    seconds_elapsed: int
) -> dict:
    distance_km = haversine_km(
        prev_lon,
        prev_lat,
        lon,
        lat
    )

    speed_kmh = 0.0
    if seconds_elapsed > 0:
        speed_kmh = (
            distance_km / seconds_elapsed
        ) * 3600

    crowd_status = random.choice(
        [
            "NOT_FULL",
            "SEMI_FULL",
            "FULL",
        ]
    )

    return {
        "busId": settings.bus_id,
        "routeId": settings.route_name,
        "lat": round(lat, 6),
        "lng": round(lon, 6),
        "speed": round(speed_kmh, 1),
        "crowdStatus": crowd_status,
        "timestamp": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime()
        ),
    }


def publish_loop():
    producer = get_producer()
    route_points = load_route_points()

    print("GPS simulator started 🚍")
    print(f"Topic: {settings.telemetry_topic}")
    print(f"Loaded {len(route_points)} route points")

    index = 1

    while running:
        prev_lon, prev_lat = route_points[index - 1]
        lon, lat = route_points[index]

        wait_seconds = random.randint(
            settings.min_interval_seconds,
            settings.max_interval_seconds
        )

        payload = create_message(
            prev_lon,
            prev_lat,
            lon,
            lat,
            wait_seconds
        )

        producer.send(
            settings.telemetry_topic,
            payload
        )
        producer.flush()

        print(
            f"Published: {payload['busId']} "
            f"lat={payload['lat']} "
            f"lng={payload['lng']} "
            f"speed={payload['speed']} km/h "
            f"crowd={payload['crowdStatus']}"
        )

        time.sleep(wait_seconds)

        index += 1

        if index >= len(route_points):
            index = 1

    producer.close()
    print("GPS simulator stopped.")


def main():
    try:
        publish_loop()
    except Exception as error:
        print(f"Simulator failed: {error}")


if __name__ == "__main__":
    main()
