import xml.etree.ElementTree as ET

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.db_route import RouteORM, StopORM


def import_kml_file(file, route_name: str, db: Session):
    """
    Parse uploaded KML file, replace route if it exists,
    then insert route + stops into database.
    """

    tree = ET.parse(file.file)
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
            lon, lat, *_ = str(point.text).strip().split(",")

            stops.append(
                {
                    "name": stop_name,
                    "lat": float(lat),
                    "lon": float(lon),
                }
            )

        # Route geometry
        elif linestring is not None:
            raw_points = str(linestring.text).strip().split()

            for pair in raw_points:
                lon, lat, *_ = pair.split(",")
                coordinates.append((float(lon), float(lat)))

    if len(coordinates) < 2:
        raise ValueError("KML route must contain at least 2 coordinates")

    if len(stops) < 2:
        raise ValueError("KML route must contain at least 2 stops")

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