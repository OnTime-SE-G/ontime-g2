# scripts/seed_routes.py

import xml.etree.ElementTree as ET
from pathlib import Path

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.models.base import Base
from scripts.models.db_route import RouteORM, StopORM
from scripts.models.route import RouteGeometry, RouteSeed, Stop
from scripts.models.settings import settings


def load_kml(file_path: str) -> RouteSeed:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"KML file not found: {file_path}")

    tree = ET.parse(path)
    root = tree.getroot()

    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    coordinates = []
    stops = []

    for placemark in root.findall(".//kml:Placemark", ns):
        name_el = placemark.find("kml:name", ns)
        name = str(name_el.text).strip() if name_el is not None else "Unnamed Stop"

        point = placemark.find(".//kml:Point/kml:coordinates", ns)
        linestring = placemark.find(".//kml:LineString/kml:coordinates", ns)

        if point is not None:
            lon, lat, *_ = str(point.text).strip().split(",")

            stops.append(
                Stop(
                    name=name,
                    lat=float(lat),
                    lon=float(lon),
                )
            )

        elif linestring is not None:
            raw_points = str(linestring.text).strip().split()

            for pair in raw_points:
                lon, lat, *_ = pair.split(",")
                coordinates.append((float(lon), float(lat)))

    geometry = RouteGeometry(coordinates=coordinates)

    return RouteSeed(
        name=settings.route_name,
        geometry=geometry,
        stops=stops,
    )


def get_engine():
    return create_engine(settings.database_url, echo=False)


def seed_database(route: RouteSeed):
    engine = get_engine()

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        existing = session.scalar(select(RouteORM).where(RouteORM.name == route.name))

        if existing:
            session.delete(existing)
            session.commit()

        line = LineString(route.geometry.coordinates)

        route_row = RouteORM(
            name=route.name,
            geometry=from_shape(line, srid=4326),
        )

        session.add(route_row)
        session.flush()

        for stop in route.stops:
            point = Point(stop.lon, stop.lat)

            stop_row = StopORM(
                route_id=route_row.id,
                name=stop.name,
                stop_order=stop.stop_order,
                location=from_shape(point, srid=4326),
            )

            session.add(stop_row)

        session.commit()

        print("Seed successful")
        print(f"Route: {route.name}")
        print(f"Stops inserted: {len(route.stops)}")


def main():
    print("Loading KML...")

    route = load_kml(settings.kml_file)
    seed_database(route)


if __name__ == "__main__":
    main()
