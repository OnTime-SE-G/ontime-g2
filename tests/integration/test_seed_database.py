# tests/integration/test_seed_database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.seed_routes import load_kml, seed_database
from scripts.models.base import Base
from scripts.models.db_route import RouteORM, StopORM
from scripts.models.settings import settings


def get_engine():
    return create_engine(settings.database_url, echo=False)


def test_seed_database_inserts_route_and_stops():
    engine = get_engine()
    Base.metadata.create_all(engine)

    route = load_kml(settings.kml_file)
    seed_database(route)

    with Session(engine) as session:
        db_route = (
            session.query(RouteORM)
            .filter(RouteORM.name == route.name)
            .first()
        )

        assert db_route is not None
        assert db_route.geometry is not None
        assert len(db_route.stops) > 0


def test_stops_have_geometry():
    engine = get_engine()

    with Session(engine) as session:
        stops = session.query(StopORM).all()

        assert len(stops) > 0

        for stop in stops:
            assert stop.location is not None