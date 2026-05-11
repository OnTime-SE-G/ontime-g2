"""Database engine, schema initialisation, and insert helper for eta_db.

PostgreSQL eta_records is a RANGE-partitioned table (monthly child partitions).
SQLAlchemy's create_all() cannot emit the PARTITION BY RANGE clause, so the
entire DDL is executed as raw SQL inside init_db().

Partition strategy
------------------
- Parent: eta_records  PARTITION BY RANGE (recorded_at)
- Children auto-named:  eta_records_YYYY_MM
- Pre-created on startup: current month + next month
- Indexes: (route_id, stop_id, recorded_at) for SARIMA range queries;
           (trip_id, recorded_at) for trip-level look-ups
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from models.eta_record import EtaRecord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine — created lazily so import alone never connects to Postgres
# ---------------------------------------------------------------------------
_engine = create_engine(
    settings.eta_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    future=True,
)

_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# Schema init (called once from main.py lifespan)
# ---------------------------------------------------------------------------

def _partition_name(year: int, month: int) -> str:
    return f"eta_records_{year:04d}_{month:02d}"


def _partition_bounds(year: int, month: int) -> tuple[str, str]:
    """Return (start_inclusive, end_exclusive) for one calendar month."""
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end_year, end_month = year + 1, 1
    else:
        end_year, end_month = year, month + 1
    end = f"{end_year:04d}-{end_month:02d}-01"
    return start, end


def _ensure_partition(conn, year: int, month: int) -> None:
    """Create a monthly child partition if it does not already exist."""
    name = _partition_name(year, month)
    start, end = _partition_bounds(year, month)
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {name}
            PARTITION OF eta_records
            FOR VALUES FROM (:start) TO (:end)
            """
        ),
        {"start": start, "end": end},
    )
    logger.debug("Ensured partition %s (%s → %s)", name, start, end)


def init_db() -> None:
    """Initialise the eta_records schema using raw DDL.

    Idempotent — safe to call on every startup.  Creates:
    - Parent table with RANGE partitioning on recorded_at
    - Indexes for SARIMA training queries and trip look-ups
    - Monthly child partitions for the current and next calendar month
    """
    with _engine.begin() as conn:
        # ---------------------------------------------------------------- #
        # 1. Parent table (partitioned)                                    #
        # ---------------------------------------------------------------- #
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS eta_records (
                    id           BIGSERIAL,
                    trip_id      TEXT        NOT NULL,
                    bus_id       TEXT        NOT NULL,
                    route_id     TEXT,
                    stop_id      INTEGER,
                    eta_seconds  DOUBLE PRECISION NOT NULL,
                    distance_m   DOUBLE PRECISION NOT NULL,
                    speed_ms     DOUBLE PRECISION NOT NULL,
                    model_used   TEXT        NOT NULL,
                    clamped      BOOLEAN     NOT NULL DEFAULT FALSE,
                    off_route    BOOLEAN     NOT NULL DEFAULT FALSE,
                    timestamp    TIMESTAMPTZ NOT NULL,
                    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (id, recorded_at)
                ) PARTITION BY RANGE (recorded_at)
                """
            )
        )

        # ---------------------------------------------------------------- #
        # 2. Indexes on parent (inherited by all partitions)               #
        # ---------------------------------------------------------------- #
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_eta_route_stop_time
                    ON eta_records (route_id, stop_id, recorded_at)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_eta_trip_time
                    ON eta_records (trip_id, recorded_at)
                """
            )
        )

        # ---------------------------------------------------------------- #
        # 3. Monthly child partitions: current month + next month          #
        # ---------------------------------------------------------------- #
        now = datetime.now(timezone.utc)
        _ensure_partition(conn, now.year, now.month)
        if now.month == 12:
            _ensure_partition(conn, now.year + 1, 1)
        else:
            _ensure_partition(conn, now.year, now.month + 1)

    logger.info("eta_records schema initialised (partitioned by recorded_at)")


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a transactional SQLAlchemy Session, rolling back on error."""
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Insert helper — called from consumer.py (non-blocking best-effort)
# ---------------------------------------------------------------------------

def insert_record(
    snapshot: dict,
    stop_id: int | None,
    off_route: bool,
) -> None:
    """Persist one ETA observation to eta_records.

    Parameters
    ----------
    snapshot   : the dict built by EtaFeatureConsumer.build_snapshot()
    stop_id    : stop identifier from the event (may be None if unavailable)
    off_route  : True when the GPS fix was flagged off-route by Flink
    """
    now_utc = datetime.now(timezone.utc)

    # Parse message timestamp (ISO 8601 or datetime)
    raw_ts = snapshot.get("timestamp") or snapshot.get("ts")
    if isinstance(raw_ts, str):
        try:
            msg_ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError:
            msg_ts = now_utc
    elif isinstance(raw_ts, datetime):
        msg_ts = raw_ts
    else:
        msg_ts = now_utc

    record = EtaRecord(
        trip_id=str(snapshot.get("tripId", "")),
        bus_id=str(snapshot.get("busId", "")),
        route_id=str(snapshot.get("routeId")) if snapshot.get("routeId") else None,
        stop_id=stop_id,
        eta_seconds=float(snapshot.get("etaSeconds", 0.0)),
        distance_m=float(snapshot.get("distanceMeters", 0.0)),
        speed_ms=float(snapshot.get("speedMs", 0.0)),
        model_used=str(snapshot.get("modelUsed", "physics")),
        clamped=bool(snapshot.get("clamped", False)),
        off_route=off_route,
        timestamp=msg_ts,
        recorded_at=now_utc,
    )

    with get_session() as session:
        session.add(record)

    logger.debug(
        "Inserted EtaRecord trip=%s stop=%s eta=%.1f s model=%s off_route=%s",
        record.trip_id,
        record.stop_id,
        record.eta_seconds,
        record.model_used,
        record.off_route,
    )
