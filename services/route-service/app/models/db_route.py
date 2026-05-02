from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.models.base import Base


class RouteStopLinkORM(Base):
    __tablename__ = "route_stop_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"), nullable=False)
    stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="CASCADE"), nullable=False)
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)

    route = relationship("RouteORM", back_populates="stop_links")
    stop = relationship("StopORM", back_populates="route_links")


class RouteORM(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_number: Mapped[str] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=True)
    destination: Mapped[str] = mapped_column(String(150), nullable=True)

    # Stores route path as a LINESTRING
    geometry = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)

    stop_links = relationship(
        "RouteStopLinkORM",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStopLinkORM.stop_order"
    )


class StopORM(Base):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    # Stores stop location as a POINT
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    route_links = relationship(
        "RouteStopLinkORM",
        back_populates="stop",
        cascade="all, delete-orphan"
    )