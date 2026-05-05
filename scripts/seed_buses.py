# scripts/seed_buses.py

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from scripts.models.base import Base
from scripts.models.db_route import RouteORM
from scripts.models.db_bus import BusORM
from scripts.models.settings import settings


def get_engine():
    return create_engine(settings.database_url, echo=False)


def seed_buses():
    engine = get_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        routes = session.scalars(select(RouteORM)).all()

        if not routes:
            raise ValueError(
                "No routes found. Run seed_routes.py first."
            )

        inserted = 0

        for route in routes:
            # remove existing buses for this route
            existing_buses = session.scalars(
                select(BusORM).where(
                    BusORM.route_id == route.id
                )
            ).all()

            for bus in existing_buses:
                session.delete(bus)

            session.flush()

            # create 3 buses per route
            for i in range(1, 4):
                bus = BusORM(
                    fleet_code=f"BUS-{route.id:03d}-{i:02d}",
                    plate_number=f"NA-{route.id:02d}{i:02d}",
                    capacity=50,
                    status="ACTIVE",
                    route_id=route.id,
                )

                session.add(bus)
                inserted += 1

        session.commit()

        print("Bus seed successful 🚌")
        print(f"Routes found: {len(routes)}")
        print(f"Buses inserted: {inserted}")


def main():
    seed_buses()


if __name__ == "__main__":
    main()