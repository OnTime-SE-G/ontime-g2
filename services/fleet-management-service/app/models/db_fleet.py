from datetime import date, time, datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import String, Integer, Time, Date, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FleetBusORM(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Unique identifiers
    fleet_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    plate_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Static configuration
    capacity: Mapped[int] = mapped_column(Integer, default=50)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")

    # Assignment (can be null if not assigned yet)
    route_id: Mapped[int] = mapped_column(Integer, nullable=True)

    # Relationships
    planned_trips: Mapped[list["PlannedTripORM"]] = relationship(back_populates="bus")


class DriverORM(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    license_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    
    # Keycloak linkage
    auth_user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    planned_trips: Mapped[list["PlannedTripORM"]] = relationship(back_populates="driver")


class ScheduleORM(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    route_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 6=Sunday

    # Relationships
    planned_trips: Mapped[list["PlannedTripORM"]] = relationship(back_populates="schedule")


class TripStatus(str, PyEnum):
    WAITING_AT_DEPOT = "WAITING_AT_DEPOT"  # Initial state (was PLANNED)
    DEPARTED_ORIGIN = "DEPARTED_ORIGIN"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED_DESTINATION = "ARRIVED_DESTINATION"  # (was COMPLETED)
    INCIDENT_REPORTED = "INCIDENT_REPORTED"
    CANCELLED = "CANCELLED"


class PlannedTripORM(Base):
    __tablename__ = "planned_trips"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # This is the trip_id
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"), nullable=False)
    bus_id: Mapped[int] = mapped_column(ForeignKey("buses.id"), nullable=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TripStatus] = mapped_column(Enum(TripStatus), default=TripStatus.WAITING_AT_DEPOT)

    # Actual performance tracking
    actual_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Delay and Incident summary
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    last_incident_type: Mapped[str] = mapped_column(String(50), nullable=True)

    # Relationships
    schedule: Mapped["ScheduleORM"] = relationship(back_populates="planned_trips")
    bus: Mapped["FleetBusORM"] = relationship(back_populates="planned_trips")
    driver: Mapped["DriverORM"] = relationship(back_populates="planned_trips")
    incidents: Mapped[list["TripIncidentORM"]] = relationship(back_populates="trip")


class TripIncidentORM(Base):
    __tablename__ = "trip_incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("planned_trips.id"), nullable=False)
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)  # BREAKDOWN, ACCIDENT, etc.
    message: Mapped[str] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trip: Mapped["PlannedTripORM"] = relationship(back_populates="incidents")