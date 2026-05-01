#services/route-service/app/services/kml_service.py

import xml.etree.ElementTree as ET

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.db_route import RouteORM, StopORM


KML_REQUIREMENTS_ERROR = "KML must contain at least 2 coordinates and 2 stops"


def parse_kml_file(file):
    try:
        tree = ET.parse(file.file)
    except ET.ParseError as exc:
        raise ValueError("Uploaded file is not valid KML") from exc

    root = tree.getroot()

    ns = {"kml": "http://www.opengis.net/kml/2.2"}

    coordinates = []
    stops = []

    for placemark in root.findall(".//kml:Placemark", ns):
        name_el = placemark.find("kml:name", ns)
        stop_name = (
            name_el.text.strip()
            if name_el is not None and name_el.text
            else "Unnamed Stop"
        )

        point = placemark.find(".//kml:Point/kml:coordinates", ns)
        linestring = placemark.find(".//kml:LineString/kml:coordinates", ns)

        # Stop point
        if point is not None:
            try:
                lon, lat, *_ = str(point.text).strip().split(",")
                lat = float(lat)
                lon = float(lon)
            except ValueError as exc:
                raise ValueError(KML_REQUIREMENTS_ERROR) from exc

            stops.append(
                {
                    "name": stop_name,
                    "lat": lat,
                    "lon": lon,
                }
            )

        # Route geometry
        elif linestring is not None:
            raw_points = str(linestring.text).strip().split()

            for pair in raw_points:
                try:
                    lon, lat, *_ = pair.split(",")
                    coordinates.append((float(lon), float(lat)))
                except ValueError as exc:
                    raise ValueError(KML_REQUIREMENTS_ERROR) from exc

    if len(coordinates) < 2 or len(stops) < 2:
        raise ValueError(KML_REQUIREMENTS_ERROR)

    return coordinates, stops


def import_kml_file(file, route_name: str, db: Session):
    """
    Parse uploaded KML file, replace route if it exists,
    then insert route + stops into database.
    """
    coordinates, stops = parse_kml_file(file)

    # Remove existing route with same name
    existing = db.scalar(
        select(RouteORM).where(RouteORM.name == route_name)
    )

    if existing:
        db.delete(existing)
        db.commit()

    # Insert route
    line = LineString(coordinates)

    route_row = RouteORM(
        name=route_name,
        geometry=from_shape(line, srid=4326),
    )

    db.add(route_row)
    db.flush()

    # Insert stops
    for index, stop in enumerate(stops, start=1):
        point = Point(stop["lon"], stop["lat"])

        stop_row = StopORM(
            route_id=route_row.id,
            name=stop["name"],
            stop_order=index,
            location=from_shape(point, srid=4326),
        )

        db.add(stop_row)

    db.commit()
    db.refresh(route_row)

    return {
        "message": "Route imported successfully",
        "route_id": route_row.id,
        "route_name": route_row.name,
        "stops_inserted": len(stops),
    }


def replace_route_from_kml_file(file, route: RouteORM, route_name: str, db: Session):
    """
    Parse uploaded KML first, then replace an existing route in place.
    """
    coordinates, stops = parse_kml_file(file)

    try:
        route.name = route_name
        route.geometry = from_shape(LineString(coordinates), srid=4326)
        route.stops.clear()

        for index, stop in enumerate(stops, start=1):
            route.stops.append(
                StopORM(
                    name=stop["name"],
                    stop_order=index,
                    location=from_shape(
                        Point(stop["lon"], stop["lat"]),
                        srid=4326,
                    ),
                )
            )

        db.commit()
        db.refresh(route)
    except SQLAlchemyError:
        db.rollback()
        raise

    return {
        "message": "Route imported successfully",
        "route_id": route.id,
        "route_name": route.name,
        "stops_inserted": len(stops),
    }
