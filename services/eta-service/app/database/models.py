"""SQLAlchemy models for eta_db."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EtaRecord(Base):
    """Persisted ETA prediction for analytics and SARIMA training."""

    __tablename__ = "eta_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(String(64), index=True)
    bus_id: Mapped[str] = mapped_column(String(64), index=True)
    route_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    stop_id: Mapped[int] = mapped_column(Integer, index=True)
    eta_seconds: Mapped[float] = mapped_column(Float)
    distance_m: Mapped[float] = mapped_column(Float)
    speed_ms: Mapped[float] = mapped_column(Float)
    model_used: Mapped[str] = mapped_column(String(32))
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    segment_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    off_route: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
