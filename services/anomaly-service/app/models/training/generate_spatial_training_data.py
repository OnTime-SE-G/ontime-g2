"""Generate synthetic normal spatial feature vectors for training the spatial IF model.

Normal scenarios modelled:
  moving        (65%) — bus travelling on-route at typical speed
  at_stop       (25%) — bus halted at a scheduled stop for a normal dwell time
  slow_traffic  (10%) — bus crawling through congestion, still on-route

The output CSV contains only "normal" observations so that IsolationForest
(an unsupervised detector) can learn the boundary of expected behaviour.
Anomalies (off-route + stuck mid-segment) are NOT included in training data;
the model learns to reject them by exclusion.

Usage:
    python -m app.models.training.generate_spatial_training_data
    python -m app.models.training.generate_spatial_training_data --n 2000 --output custom.csv
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

SPATIAL_FEATURE_COLUMNS = [
    "route_deviation_meters",
    "speed_kmh",
    "stationary_duration_sec",
    "distance_to_next_stop_m",
    "route_progress_pct",
]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def generate_normal_samples(n: int, seed: int = 42) -> list[dict]:
    """Return *n* synthetic normal spatial feature vectors."""
    rng = random.Random(seed)
    samples: list[dict] = []

    for _ in range(n):
        scenario = rng.choices(
            ["moving", "at_stop", "slow_traffic"],
            weights=[0.65, 0.25, 0.10],
        )[0]

        # GPS horizontal accuracy typically 3-15 m on-route
        deviation = _clamp(rng.gauss(6, 4), 0.0, 30.0)
        progress = rng.uniform(0.0, 100.0)

        if scenario == "moving":
            speed = _clamp(rng.gauss(30, 12), 8.0, 65.0)
            stationary_dur = 0.0
            dist_to_stop = rng.uniform(100.0, 5500.0)

        elif scenario == "at_stop":
            # Normal dwell: 10 s – 3 min; bus IS at or very close to the stop
            speed = 0.0
            stationary_dur = _clamp(rng.gauss(60, 25), 10.0, 180.0)
            dist_to_stop = _clamp(rng.gauss(15, 10), 0.0, 60.0)

        else:  # slow_traffic — crawling but still moving
            speed = _clamp(rng.gauss(6, 3), 0.0, 18.0)
            stationary_dur = _clamp(rng.gauss(35, 20), 0.0, 120.0)
            dist_to_stop = rng.uniform(50.0, 5000.0)

        samples.append(
            {
                "route_deviation_meters": round(deviation, 2),
                "speed_kmh": round(speed, 2),
                "stationary_duration_sec": round(stationary_dur, 1),
                "distance_to_next_stop_m": round(dist_to_stop, 1),
                "route_progress_pct": round(progress, 2),
            }
        )

    return samples


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic normal spatial training data for the anomaly IF model"
    )
    parser.add_argument("--n", type=int, default=1200, help="Number of samples (default: 1200)")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("spatial_train.csv"),
        help="Output CSV path",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    samples = generate_normal_samples(args.n, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SPATIAL_FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(samples)

    print(f"Wrote {len(samples)} normal samples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
