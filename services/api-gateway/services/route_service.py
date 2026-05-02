# services/api-gateway/services/route_service.py
# ORM-backed queries for routes, stops, and buses.

from typing import Optional

from sqlalchemy.orm import Session

from scripts.models.db_route import RouteORM, StopORM
from scripts.models.db_bus import BusORM


def list_routes(db: Session) -> list[RouteORM]:
    return db.query(RouteORM).order_by(RouteORM.id).all()


def get_route(db: Session, route_id: int) -> Optional[RouteORM]:
    return db.query(RouteORM).filter(RouteORM.id == route_id).first()


def list_buses(db: Session) -> list[BusORM]:
    return db.query(BusORM).order_by(BusORM.id).all()


def get_bus(db: Session, bus_id: int) -> Optional[BusORM]:
    return db.query(BusORM).filter(BusORM.id == bus_id).first()


def get_stops_for_route(db: Session, route_id: int) -> list[StopORM]:
    return (
        db.query(StopORM)
        .filter(StopORM.route_id == route_id)
        .order_by(StopORM.stop_order)
        .all()
    )


def get_stop(db: Session, stop_id: int) -> Optional[StopORM]:
    return db.query(StopORM).filter(StopORM.id == stop_id).first()
