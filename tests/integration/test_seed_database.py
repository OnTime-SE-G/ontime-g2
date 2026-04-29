# tests/integration/test_seed_database.py

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from scripts.seed_routes import discover_kml_files, load_kml, seed_database
from scripts.models.base import Base
from scripts.models.db_route import RouteORM, StopORM
from scripts.models.settings import settings

# Add the api-gateway service root to sys.path for importing main.py
API_GATEWAY_ROOT = Path(__file__).resolve().parents[2] / "services" / "api-gateway"
if str(API_GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(API_GATEWAY_ROOT))



def get_engine():
    return create_engine(settings.database_url, echo=False)


def db_is_reachable() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def test_seed_database_inserts_route_and_stops():
    if not db_is_reachable():
        pytest.skip(
            "Postgres is not reachable in current environment. Run via docker compose for integration checks."
        )

    engine = get_engine()
    Base.metadata.create_all(engine)

    route_file = discover_kml_files(settings.data_dir)[0]
    route = load_kml(route_file)
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
    if not db_is_reachable():
        pytest.skip(
            "Postgres is not reachable in current environment. Run via docker compose for integration checks."
        )

    engine = get_engine()

    with Session(engine) as session:
        stops = session.query(StopORM).all()

        assert len(stops) > 0

        for stop in stops:
            assert stop.location is not None
