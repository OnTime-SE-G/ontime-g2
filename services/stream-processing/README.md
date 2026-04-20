# Stream Processing Service

Processes live telemetry streams and enriches them for downstream services.

## Responsibilities

- Filter/clean GPS noise
- Enrich records with route context
- Prepare features for ETA and anomaly services

## Notes

- Increment 1 can start with lightweight consumers.
- Flink-based pipelines can be introduced after baseline flow is stable.

## Ownership and Review

- Owner: Chamodh
- Required reviewer: Nathasha
- Optional reviewer: Nidharshan
