"""Export eta_db records for SARIMA and supervised retraining."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


def export_eta_records(output_path: Path, *, limit: int | None = None) -> Path:
    database_url = os.environ.get(
        "ETA_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/eta_db",
    )
    engine = create_engine(database_url)
    query = "SELECT * FROM eta_records ORDER BY recorded_at DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    frame = pd.read_sql(text(query), engine)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export eta_db ETA records")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("ml/data/eta_db_records.csv"),
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    path = export_eta_records(args.out, limit=args.limit)
    print(f"Exported eta_db rows to {path} at {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
