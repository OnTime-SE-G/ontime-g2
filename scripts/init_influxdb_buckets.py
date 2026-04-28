#!/usr/bin/env python3
"""
Create additional InfluxDB buckets that are not auto-created by docker-compose.

docker-compose already creates the 'telemetry' bucket via DOCKER_INFLUXDB_INIT_BUCKET.
This script creates 'eta_predictions' (and any other buckets listed in EXTRA_BUCKETS).

Usage:
    set -a && source docker/.env && set +a
    python scripts/init_influxdb_buckets.py

Requires:
    pip install influxdb-client
Environment vars (all present in docker/.env.example):
    INFLUXDB_URL            e.g. http://localhost:8086
    INFLUXDB_ADMIN_TOKEN    admin token set during InfluxDB init
    INFLUXDB_INIT_ORG       e.g. ontime
"""
from __future__ import annotations

import os
import sys

EXTRA_BUCKETS = ["eta_predictions"]


def main() -> None:
    try:
        from influxdb_client import InfluxDBClient  # type: ignore[import]
    except ModuleNotFoundError:
        print("ERROR: influxdb-client is not installed.\n  pip install influxdb-client")
        sys.exit(1)

    url = os.environ.get("INFLUXDB_URL", "http://localhost:8086")
    token = os.environ.get("INFLUXDB_ADMIN_TOKEN")
    org = os.environ.get("INFLUXDB_INIT_ORG", "ontime")

    if not token:
        print(
            "ERROR: INFLUXDB_ADMIN_TOKEN is not set.\n"
            "  Run: set -a && source docker/.env && set +a"
        )
        sys.exit(1)

    client = InfluxDBClient(url=url, token=token, org=org)
    buckets_api = client.buckets_api()

    try:
        existing = {b.name for b in buckets_api.find_buckets().buckets}
    except Exception as exc:
        print(f"ERROR: Could not reach InfluxDB at {url}.\n  {exc}")
        client.close()
        sys.exit(1)

    print(f"Connected to InfluxDB at {url} (org={org})")
    for name in EXTRA_BUCKETS:
        if name in existing:
            print(f"  Bucket '{name}' already exists — skipping.")
        else:
            buckets_api.create_bucket(bucket_name=name, org=org)
            print(f"  ✓ Created bucket '{name}'")

    client.close()
    print("Done.")


if __name__ == "__main__":
    main()
