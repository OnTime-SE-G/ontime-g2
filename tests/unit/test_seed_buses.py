# tests/unit/test_seed_buses.py

import pytest
from sqlalchemy import Column, Integer, String, create_engine, select, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session

from scripts.models.db_bus import BusORM
from scripts.seed_buses import seed_buses


@pytest.fixture
def engine(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    TestBase = declarative_base()

    class TestRouteORM(TestBase):
        __tablename__ = "routes"

        id = Column(Integer, primary_key=True)
        name = Column(String(150), unique=True, nullable=False)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE routes (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(150) UNIQUE NOT NULL,
                    geometry TEXT
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE buses (
                    id INTEGER PRIMARY KEY,
                    fleet_code VARCHAR(50) UNIQUE NOT NULL,
                    plate_number VARCHAR(50) UNIQUE NOT NULL,
                    capacity INTEGER,
                    status VARCHAR(20),
                    route_id INTEGER NOT NULL,
                    FOREIGN KEY(route_id) REFERENCES routes(id)
                )
                """
            )
        )

    import scripts.seed_buses as seed_module

    monkeypatch.setattr(
        seed_module,
        "RouteORM",
        TestRouteORM
    )
    monkeypatch.setattr(
        seed_module,
        "get_engine",
        lambda: engine
    )
    monkeypatch.setattr(
        seed_module.Base.metadata,
        "create_all",
        lambda _engine: None
    )

    return engine


@pytest.fixture
def seeded_route(engine):
    with engine.begin() as connection:
        result = connection.execute(
            text(
                """
                INSERT INTO routes (name, geometry)
                VALUES (:name, :geometry)
                """
            ),
            {
                "name": "Test Route",
                "geometry": "LINESTRING(79.1 7.1, 79.2 7.2)",
            }
        )

        return result.lastrowid


def test_seed_buses_raises_if_no_routes(engine):
    with pytest.raises(ValueError, match="No routes found"):
        seed_buses()


def test_seed_buses_inserts_three_buses_per_route(
    engine,
    seeded_route
):
    seed_buses()

    with Session(engine) as session:
        buses = session.scalars(
            select(BusORM)
        ).all()

        assert len(buses) == 3


def test_seed_buses_assigns_correct_route_id(
    engine,
    seeded_route
):
    seed_buses()

    with Session(engine) as session:
        buses = session.scalars(
            select(BusORM)
        ).all()

        for bus in buses:
            assert bus.route_id == seeded_route


def test_seed_buses_generates_fleet_codes(
    engine,
    seeded_route
):
    seed_buses()

    with Session(engine) as session:
        buses = session.scalars(
            select(BusORM)
        ).all()

        fleet_codes = [bus.fleet_code for bus in buses]

        assert "BUS-001-01" in fleet_codes
        assert "BUS-001-02" in fleet_codes
        assert "BUS-001-03" in fleet_codes


def test_seed_buses_replaces_existing_buses(
    engine,
    seeded_route
):
    seed_buses()
    seed_buses()

    with Session(engine) as session:
        buses = session.scalars(
            select(BusORM)
        ).all()

        assert len(buses) == 3


def test_seed_buses_sets_defaults(
    engine,
    seeded_route
):
    seed_buses()

    with Session(engine) as session:
        bus = session.scalar(select(BusORM))

        assert bus is not None
        assert bus.capacity == 50
        assert bus.status == "ACTIVE"
