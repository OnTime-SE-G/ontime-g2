"""
generate_data.py — Synthetic training data for the XGBoost ETA model (Inc 2, K-7).

Features:
    distance_m       — metres from bus to stop (50–15000)
    speed_ms         — bus speed in m/s (0.5–20)
    hour_of_day      — 0–23
    day_of_week      — 0 Monday … 6 Sunday
    is_weekend       — 1 if day_of_week >= 5 else 0
    stops_remaining  — 1–20
    physics_eta      — distance_m / max(speed_ms, 1.4) before traffic multiplier

Target:
    eta_seconds      — physics formula with traffic multiplier + Gaussian noise

Traffic multipliers:
    rush hour (7–9am, 17–19) weekday: ×1.25  (buses slow down)
    weekend midday (11–14):            ×1.15
    otherwise:                         ×1.00

Usage:
    python3 generate_data.py              → saves training_data.csv in same directory
    python3 generate_data.py --samples N  → override sample count (default 5000)
"""

import argparse
import csv
import math
import os
import random

_MIN_SPEED_MS = 1.4
_NOISE_FRACTION = 0.12   # ±12% Gaussian noise on final ETA


def _traffic_multiplier(hour: int, dow: int) -> float:
    is_weekend = dow >= 5
    if not is_weekend and hour in range(7, 10):   # weekday morning rush
        return 1.25
    if not is_weekend and hour in range(17, 20):  # weekday evening rush
        return 1.25
    if is_weekend and hour in range(11, 15):      # weekend midday
        return 1.15
    return 1.00


def generate_sample(rng: random.Random) -> dict:
    distance_m = rng.uniform(50, 15000)
    speed_ms = rng.uniform(0.5, 20.0)
    hour = rng.randint(0, 23)
    dow = rng.randint(0, 6)
    is_weekend = 1 if dow >= 5 else 0
    stops_remaining = rng.randint(1, 20)

    effective_speed = max(speed_ms, _MIN_SPEED_MS)
    physics_eta = distance_m / effective_speed
    multiplier = _traffic_multiplier(hour, dow)
    base_eta = physics_eta * multiplier

    # Gaussian noise
    noise = rng.gauss(0, base_eta * _NOISE_FRACTION)
    eta_seconds = max(0.0, base_eta + noise)

    return {
        "distance_m": round(distance_m, 2),
        "speed_ms": round(speed_ms, 4),
        "hour_of_day": hour,
        "day_of_week": dow,
        "is_weekend": is_weekend,
        "stops_remaining": stops_remaining,
        "physics_eta": round(physics_eta, 2),
        "eta_seconds": round(eta_seconds, 2),
    }


def generate(n_samples: int = 5000, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    return [generate_sample(rng) for _ in range(n_samples)]


def save_csv(samples: list[dict], path: str) -> None:
    fieldnames = list(samples[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
    print(f"Saved {len(samples)} samples → {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic ETA training data")
    parser.add_argument("--samples", type=int, default=5000, help="Number of samples (default 5000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--out", type=str, default=None, help="Output CSV path")
    args = parser.parse_args()

    out_path = args.out or os.path.join(os.path.dirname(__file__), "training_data.csv")
    samples = generate(n_samples=args.samples, seed=args.seed)
    save_csv(samples, out_path)
