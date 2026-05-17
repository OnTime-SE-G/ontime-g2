"""SQLAlchemy ORM model for the eta_records table.

The table uses PostgreSQL declarative RANGE partitioning on `recorded_at`
(one partition per calendar month).  SQLAlchemy cannot create a partitioned
parent table via create_all(), so the DDL is handled by eta_db.init_db()
using raw SQL.  This ORM class is used purely for INSERT operations — the
database routes each insert to the correct monthly child partition
automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EtaRecord(Base):
    """One ETA prediction stored for retrospective analysis and SARIMA training.

    Columns
    -------
    id            : auto-increment surrogate key (propagated to each partition)
    trip_id       : active trip identifier at prediction time
    bus_id        : bus that was serving the trip
    route_id      : route the bus is assigned to (nullable — GPS noise edge case)
    stop_id       : stop for which ETA was computed
    eta_seconds   : predicted seconds until bus reaches stop_id
    distance_m    : metres from bus to stop at prediction time
    speed_ms      : effective speed used in the computation (post-clamp)
    model_used    : 'physics' | 'xgboost' | 'sarima'
    clamped       : True when speed was below _MIN_SPEED_MS and was clamped
    off_route     : True when the GPS fix was flagged off-route by Flink
                    (records with off_route=True are excluded from SARIMA training)
    timestamp     : ISO 8601 UTC timestamp from the GPS / Flink message
    recorded_at   : wall-clock time the ETA Service inserted this row
                    (partition key — determines which monthly child receives the row)
    """

    __tablename__ = "eta_records"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(Text, nullable=False)
    bus_id: Mapped[str] = mapped_column(Text, nullable=False)
    route_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stop_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    speed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    clamped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    off_route: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        primary_key=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
