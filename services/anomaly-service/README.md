# Anomaly Service

Rule-based alerting for G2 telemetry.

## Inputs

| Topic | Purpose |
|-------|---------|
| `transport-telemetry-cleaned` | enriched GPS telemetry from Flink |
| `transport-telemetry-dlq` | rejected GPS envelopes from ingestion |

## Output

| Topic | Purpose |
|-------|---------|
| `transport-anomaly-alerts` | anomaly/operations alerts for admin, API, and monitoring |

## Current Rules

- `UNREALISTIC_SPEED`: cleaned telemetry speed is above the safe threshold.
- `OFF_ROUTE`: cleaned telemetry is too far from the route geometry.
- `STATIONARY`: bus remains under the stationary speed threshold for too long.
- `COMMUNICATION_LOSS`: an active bus stops sending cleaned telemetry.
- `TRIP_NOT_STARTED_DEVICE_ACTIVE`: ingestion repeatedly sends `INACTIVE_TRIP`
  DLQ events for the same bus, meaning the device is on but no driver-started
  trip exists.

## DLQ Inactive-Trip Logic

The service does not alert on a single inactive GPS packet. It waits for repeated
DLQ events from the same `busId`:

- default threshold: 3 `INACTIVE_TRIP` DLQ events
- default window: 60 seconds
- default cooldown: 300 seconds before another alert for the same bus

This keeps startup/cache timing noise from becoming a false alert.

## Configuration

| Env var | Default |
|---------|---------|
| `KAFKA_BROKER_URL` | `broker:29092` |
| `KAFKA_CLEANED_TOPIC` | `transport-telemetry-cleaned` |
| `KAFKA_DLQ_TOPIC` | `transport-telemetry-dlq` |
| `KAFKA_ANOMALY_TOPIC` | `transport-anomaly-alerts` |
| `KAFKA_DLQ_GROUP_ID` | `anomaly-service-dlq-group` |
| `ROUTE_SERVICE_URL` | `http://route-service:8002` |
| `INACTIVE_TRIP_DLQ_THRESHOLD_COUNT` | `3` |
| `INACTIVE_TRIP_DLQ_WINDOW_SECONDS` | `60` |
| `INACTIVE_TRIP_DLQ_COOLDOWN_SECONDS` | `300` |

## Health

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`
