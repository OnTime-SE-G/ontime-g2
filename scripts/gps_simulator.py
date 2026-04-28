# scripts/gps_simulator.py
# GPS Simulator - publishes simulated bus GPS telemetry via MQTT.
# The Ingestion Service subscribes to MQTT and bridges validated messages to Kafka.

import json
import math
import random
import signal
import time
from typing import List, Tuple

import paho.mqtt.client as mqtt
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


def get_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(
        client_id=f"gps-simulator-{settings.bus_id}",
        protocol=mqtt.MQTTv311,
    )

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker at {settings.mqtt_broker_host}:{settings.mqtt_broker_port}")
        else:
            print(f"MQTT connection failed with code {rc}")

    def on_disconnect(client, userdata, rc):
        if rc != 0:
            print(f"Unexpected MQTT disconnect (code {rc}). Will auto-reconnect.")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.connect(
        settings.mqtt_broker_host,
        settings.mqtt_broker_port,
    )
    client.loop_start()
    return client


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


def calculate_bearing(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float
) -> float:
    """Calculate bearing (heading) in degrees between two GPS points."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlon_r = math.radians(lon2 - lon1)

    x = math.sin(dlon_r) * math.cos(lat2_r)
    y = (
        math.cos(lat1_r) * math.sin(lat2_r)
        - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon_r)
    )

    bearing = math.degrees(math.atan2(x, y))
    return round(bearing % 360, 1)


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

    heading = calculate_bearing(
        prev_lon,
        prev_lat,
        lon,
        lat
    )

    return {
        "busId": settings.bus_id,
        "tripId": settings.trip_id,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "speed": round(speed_kmh, 1),
        "heading": heading,
        "timestamp": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime()
        ),
    }


def publish_loop():
    client = get_mqtt_client()
    route_points = load_route_points()
    mqtt_topic = f"transport/bus/{settings.bus_id}/location"

    print("GPS simulator started (MQTT mode) 🚍")
    print(f"MQTT topic: {mqtt_topic}")
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

        result = client.publish(
            mqtt_topic,
            json.dumps(payload),
        )
        result.wait_for_publish()

        print(
            f"Published: {payload['busId']} "
            f"lat={payload['lat']} "
            f"lon={payload['lon']} "
            f"speed={payload['speed']} km/h "
            f"heading={payload['heading']}°"
        )

        time.sleep(wait_seconds)

        index += 1

        if index >= len(route_points):
            index = 1

    client.loop_stop()
    client.disconnect()
    print("GPS simulator stopped.")


def main():
    try:
        publish_loop()
    except Exception as error:
        print(f"Simulator failed: {error}")


if __name__ == "__main__":
    main()
