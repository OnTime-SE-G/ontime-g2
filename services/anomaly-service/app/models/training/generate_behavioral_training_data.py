"""Generate synthetic CSV for behavioral Isolation Forest training."""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

COLUMNS = [
    "max_acceleration",
    "min_acceleration",
    "speed_variance",
    "heading_variance",
    "average_speed",
    "sample_count",
]


def _normal_sample(rng: random.Random) -> dict[str, float]:
    return {
        "max_acceleration": round(rng.uniform(0.5, 2.5), 4),
        "min_acceleration": round(rng.uniform(-2.5, -0.5), 4),
        "speed_variance": round(rng.uniform(0.1, 3.0), 4),
        "heading_variance": round(rng.uniform(0.05, 1.5), 4),
        "average_speed": round(rng.uniform(15.0, 55.0), 4),
        "sample_count": float(rng.randint(15, 25)),
    }


def _erratic_sample(rng: random.Random) -> dict[str, float]:
    return {
        "max_acceleration": round(rng.uniform(3.0, 8.0), 4),
        "min_acceleration": round(rng.uniform(-8.0, -3.0), 4),
        "speed_variance": round(rng.uniform(8.0, 25.0), 4),
        "heading_variance": round(rng.uniform(5.0, 20.0), 4),
        "average_speed": round(rng.uniform(5.0, 90.0), 4),
        "sample_count": float(rng.randint(15, 25)),
    }


def generate(n_samples: int = 2000, seed: int = 42) -> list[dict[str, float]]:
    rng = random.Random(seed)
    rows: list[dict[str, float]] = []
    for _ in range(n_samples):
        if rng.random() < 0.05:
            rows.append(_erratic_sample(rng))
        else:
            rows.append(_normal_sample(rng))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate behavioral IF training CSV")
    parser.add_argument("--samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "behavioral_train.csv",
    )
    args = parser.parse_args()
    rows = generate(n_samples=args.samples, seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
