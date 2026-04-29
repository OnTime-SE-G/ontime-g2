from sqlalchemy import select
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from database import get_engine
from scripts.models.db_route import RouteORM, StopORM


def fetch_routes():
    engine = get_engine()

    with Session(engine) as session:
        routes = session.scalars(select(RouteORM)).all()

        return [
            {
                "id": route.id,
                "name": route.name,
            }
            for route in routes
        ]


def fetch_route(route_id: int):
    engine = get_engine()

    with Session(engine) as session:
        route = session.get(RouteORM, route_id)

        if route is None:
            return None

        line = to_shape(route.geometry)

        return {
            "id": route.id,
            "name": route.name,
            "coordinates": [
                [float(x), float(y)]
                for x, y in line.coords
            ],
        }


def fetch_route_stops(route_id: int):
    engine = get_engine()

    with Session(engine) as session:
        stops = session.scalars(
            select(StopORM)
            .where(StopORM.route_id == route_id)
            .order_by(StopORM.stop_order)
        ).all()

        result = []

        for stop in stops:
            point = to_shape(stop.location)

            result.append(
                {
                    "id": stop.id,
                    "name": stop.name,
                    "order": stop.stop_order,
                    "lat": point.y,
                    "lng": point.x,
                }
            )

        return result