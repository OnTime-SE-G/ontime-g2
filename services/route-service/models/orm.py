from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry

from models.base import Base


class RouteORM(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    geometry = mapped_column(Geometry("LINESTRING", srid=4326))

    stops = relationship("StopORM", back_populates="route", cascade="all, delete-orphan")
    buses = relationship("BusORM", back_populates="route", cascade="all, delete-orphan")


class StopORM(Base):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    stop_order: Mapped[int] = mapped_column(Integer, nullable=False)
    location = mapped_column(Geometry("POINT", srid=4326))

    route = relationship("RouteORM", back_populates="stops")


class BusORM(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    plate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    route = relationship("RouteORM", back_populates="buses")
