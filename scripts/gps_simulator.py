# scripts/gps_simulator.py

import json
import math
import random
import signal
import time
from typing import Dict, List, Tuple

import paho.mqtt.client as mqtt
from geoalchemy2.shape import to_shape
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.models.db_bus import BusORM
from scripts.models.db_route import RouteORM
from scripts.models.settings import settings


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
    client = mqtt.Client()

    client.connect(
        settings.mqtt_broker_host,
        settings.mqtt_broker_port,
        60
    )

    client.loop_start()
    return client


def now_utc() -> str:
    return time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime()
    )


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

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

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


def create_status_message(
    bus_id: int,
    route_id: int,
    status: str
) -> dict:
    return {
        "type": "STATUS",
        "status": status,
        "busId": bus_id,
        "routeId": route_id,
        "timestamp": now_utc(),
    }


def create_location_message(
    bus_id: int,
    route_id: int,
    prev_lon: float,
    prev_lat: float,
    lon: float,
    lat: float
) -> dict:
    heading = calculate_bearing(prev_lon, prev_lat, lon, lat)
    
    return {
        "busId": str(bus_id),
        "tripId": f"TRIP_{bus_id}",
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "speed": random.randint(30, 50),
        "heading": heading,
        "timestamp": now_utc(),
    }


def publish_json(
    client: mqtt.Client,
    topic: str,
    payload: dict
):
    client.publish(
        topic,
        json.dumps(payload),
        qos=1
    )


def load_routes_and_buses():
    engine = get_engine()

    with Session(engine) as session:
        routes = session.scalars(
            select(RouteORM)
        ).all()

        if not routes:
            raise ValueError(
                "No routes found. Run seed_routes.py first."
            )

        buses = session.scalars(
            select(BusORM)
        ).all()

        if not buses:
            raise ValueError(
                "No buses found. Run seed_buses.py first."
            )

        buses_by_route: Dict[int, List[BusORM]] = {}

        for bus in buses:
            buses_by_route.setdefault(
                bus.route_id,
                []
            ).append(bus)

        route_points: Dict[
            int,
            List[Tuple[float, float]]
        ] = {}

        for route in routes:
            line = to_shape(route.geometry)

            route_points[route.id] = [
                (float(coord[0]), float(coord[1]))
                for coord in line.coords
            ]

        return routes, buses_by_route, route_points


def choose_next_bus(
    route_id: int,
    buses_by_route: Dict[int, List[BusORM]],
    active_bus_id: int | None = None
):
    candidates = buses_by_route.get(route_id, [])

    if not candidates:
        return None

    available = [
        bus for bus in candidates
        if bus.id != active_bus_id
    ]

    if not available:
        available = candidates

    return random.choice(available)


def publish_loop():
    client = get_mqtt_client()

    (
        routes,
        buses_by_route,
        route_points
    ) = load_routes_and_buses()

    print("GPS simulator started 🚌")

    route_state = {}

    for route in routes:
        bus = choose_next_bus(
            route.id,
            buses_by_route
        )

        if bus is None:
            continue

        route_state[route.id] = {
            "bus": bus,
            "index": 0,
        }

        topic_status = (
            f"transport/bus/"
            f"{bus.id}/status"
        )

        start_payload = create_status_message(
            bus.id,
            route.id,
            "STARTED"
        )

        publish_json(
            client,
            topic_status,
            start_payload
        )

        print(
            f"STARTED bus={bus.id} "
            f"route={route.id}"
        )

    while running:
        for route in routes:
            state = route_state.get(route.id)

            if state is None:
                continue

            bus = state["bus"]
            index = state["index"]

            points = route_points[route.id]

            if index >= len(points) - 1:
                topic_status = (
                    f"transport/bus/"
                    f"{bus.id}/status"
                )

                stop_payload = create_status_message(
                    bus.id,
                    route.id,
                    "STOPPED"
                )

                publish_json(
                    client,
                    topic_status,
                    stop_payload
                )

                print(
                    f"STOPPED bus={bus.id} "
                    f"route={route.id}"
                )

                next_bus = choose_next_bus(
                    route.id,
                    buses_by_route,
                    bus.id
                )

                if next_bus is None:
                    continue

                route_state[route.id] = {
                    "bus": next_bus,
                    "index": 0,
                }

                next_topic_status = (
                    f"transport/bus/"
                    f"{next_bus.id}/status"
                )

                start_payload = create_status_message(
                    next_bus.id,
                    route.id,
                    "STARTED"
                )

                publish_json(
                    client,
                    next_topic_status,
                    start_payload
                )

                print(
                    f"STARTED bus={next_bus.id} "
                    f"route={route.id}"
                )

                continue

            prev_lon, prev_lat = points[index]
            lon, lat = points[index + 1]

            wait_seconds = random.randint(
                settings.min_interval_seconds,
                settings.max_interval_seconds
            )

            payload = create_location_message(
                bus.id,
                route.id,
            prev_lon,
            prev_lat,
            lon,
            lat
        )

            topic = (
                f"transport/bus/"
                f"{bus.id}/location"
            )

            publish_json(
                client,
                topic,
                payload
            )

            print(
                f"LOCATION bus={bus.id} "
                f"route={route.id} "
                f"lat={payload['lat']} "
                f"lon={payload['lon']} "
                f"heading={payload['heading']}°"
            )

            state["index"] = index + 1

        time.sleep(
            random.randint(
                settings.min_interval_seconds,
                settings.max_interval_seconds
            )
        )

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
