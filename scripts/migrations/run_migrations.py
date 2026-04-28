#!/usr/bin/env python3
"""
Apply SQL migrations in order against the configured PostgreSQL database.

Usage:
    # Load vars from docker/.env first, then run:
    set -a && source docker/.env && set +a
    python scripts/migrations/run_migrations.py

Requires DATABASE_URL environment variable.
Already-applied migrations are tracked in the schema_migrations table and skipped.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PGConnection

MIGRATIONS_DIR = Path(__file__).parent


def _get_connection() -> PGConnection:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print(
            "ERROR: DATABASE_URL is not set.\n"
            "  Run: set -a && source docker/.env && set +a"
        )
        sys.exit(1)
    try:
        return psycopg2.connect(url)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Could not connect to PostgreSQL.\n  {exc}")
        sys.exit(1)


def _ensure_tracking_table(conn: PGConnection) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     VARCHAR(255) PRIMARY KEY,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
    conn.commit()


def _applied_versions(conn: PGConnection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations;")
        return {row[0] for row in cur.fetchall()}


def _apply(conn: PGConnection, sql_file: Path) -> None:
    version = sql_file.stem  # e.g. "V1__create_routes_and_stops"
    sql = sql_file.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s);",
            (version,),
        )
    conn.commit()


def main() -> None:
    sql_files = sorted(MIGRATIONS_DIR.glob("V*.sql"))
    if not sql_files:
        print("No migration files found in", MIGRATIONS_DIR)
        sys.exit(0)

    conn = _get_connection()
    _ensure_tracking_table(conn)
    applied = _applied_versions(conn)

    pending = [f for f in sql_files if f.stem not in applied]
    if not pending:
        print("All migrations already applied. Nothing to do.")
        conn.close()
        sys.exit(0)

    print(f"Applying {len(pending)} migration(s)...")
    for f in pending:
        print(f"  → {f.name}", end="", flush=True)
        try:
            _apply(conn, f)
            print(" ✓")
        except Exception as exc:
            conn.rollback()
            print(f" FAILED\n  {exc}")
            conn.close()
            sys.exit(1)

    print(f"\nDone. {len(pending)} migration(s) applied.")
    conn.close()


if __name__ == "__main__":
    main()
