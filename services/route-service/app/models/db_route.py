from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from app.models.base import Base


class RouteORM(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)

    # Stores route path as a LINESTRING
    geometry = mapped_column(Geometry("LINESTRING", srid=4326), nullable=True)

    stops = relationship(
        "StopORM",
        back_populates="route",
        cascade="all, delete-orphan"
    )


class StopORM(Base):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Stores stop location as a POINT
    location = mapped_column(Geometry("POINT", srid=4326), nullable=True)

    route = relationship("RouteORM", back_populates="stops")