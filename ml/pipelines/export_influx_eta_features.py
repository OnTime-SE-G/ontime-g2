"""Export enriched telemetry from InfluxDB for ETA model training."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def export_features(
    output_path: Path,
    *,
    days: int = 30,
) -> Path:
    url = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
    token = os.environ.get("INFLUXDB_TOKEN", "")
    org = os.environ.get("INFLUXDB_ORG", "ontime")
    bucket = os.environ.get("INFLUXDB_BUCKET", "telemetry")

    if not token:
        raise RuntimeError("INFLUXDB_TOKEN is required to export training data")

    from influxdb_client import InfluxDBClient

    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -{days}d)
      |> filter(fn: (r) => r._measurement == "telemetry")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    with InfluxDBClient(url=url, token=token, org=org) as client:
        tables = client.query_api().query_data_frame(query)

    if isinstance(tables, list):
        frame = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    else:
        frame = tables

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export InfluxDB telemetry for ETA training")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("ml/data/influx_eta_features.csv"),
    )
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    path = export_features(args.out, days=args.days)
    print(f"Exported Influx features to {path} at {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
