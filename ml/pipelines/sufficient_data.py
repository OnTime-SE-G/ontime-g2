"""Check whether enough data exists to run a production retrain."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class DataSufficiencyResult:
    sufficient: bool
    influx_days: float
    eta_record_count: int
    sarima_ready_stops: int
    reasons: list[str]


def check_data_sufficiency(
    *,
    min_influx_days: float | None = None,
    min_eta_records: int | None = None,
    min_sarima_stops: int | None = None,
) -> DataSufficiencyResult:
    """Evaluate training data thresholds from environment or defaults."""
    min_days = float(min_influx_days or os.environ.get("RETRAIN_MIN_INFLUX_DAYS", "7"))
    min_records = int(min_eta_records or os.environ.get("RETRAIN_MIN_ETA_RECORDS", "500"))
    min_stops = int(min_sarima_stops or os.environ.get("RETRAIN_MIN_SARIMA_STOPS", "1"))

    reasons: list[str] = []
    influx_days = _estimate_influx_days()
    eta_count = _count_eta_records()
    sarima_stops = _count_sarima_ready_stops()

    if influx_days < min_days:
        reasons.append(f"influx_days {influx_days:.1f} < {min_days}")
    if eta_count < min_records:
        reasons.append(f"eta_records {eta_count} < {min_records}")

    sufficient = not reasons
    return DataSufficiencyResult(
        sufficient=sufficient,
        influx_days=influx_days,
        eta_record_count=eta_count,
        sarima_ready_stops=sarima_stops,
        reasons=reasons,
    )


def _estimate_influx_days() -> float:
    url = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
    token = os.environ.get("INFLUXDB_TOKEN", "")
    org = os.environ.get("INFLUXDB_ORG", "ontime")
    bucket = os.environ.get("INFLUXDB_BUCKET", "telemetry")
    if not token:
        return 0.0
    try:
        from influxdb_client import InfluxDBClient

        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -30d)
          |> filter(fn: (r) => r._measurement == "telemetry")
          |> keep(columns: ["_time"])
          |> first()
        '''
        with InfluxDBClient(url=url, token=token, org=org) as client:
            tables = client.query_api().query(query)
            if not tables or not tables[0].records:
                return 0.0
            first_time = tables[0].records[0].get_time()
            if first_time.tzinfo is None:
                first_time = first_time.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - first_time
            return max(delta.total_seconds() / 86400.0, 0.0)
    except Exception:
        return 0.0


def _count_eta_records() -> int:
    database_url = os.environ.get(
        "ETA_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/eta_db",
    )
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM eta_records"))
            row = result.scalar()
            return int(row or 0)
    except Exception:
        return 0


def _count_sarima_ready_stops() -> int:
    database_url = os.environ.get(
        "ETA_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/eta_db",
    )
    threshold_hours = int(os.environ.get("SARIMA_MIN_THRESHOLD_HOURS", "48"))
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(database_url)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
        query = text(
            """
            SELECT COUNT(*) FROM (
              SELECT route_id, stop_id
              FROM eta_records
              WHERE recorded_at >= :cutoff
              GROUP BY route_id, stop_id
              HAVING COUNT(*) >= 10
            ) ready
            """
        )
        with engine.connect() as conn:
            result = conn.execute(query, {"cutoff": cutoff})
            return int(result.scalar() or 0)
    except Exception:
        return 0
