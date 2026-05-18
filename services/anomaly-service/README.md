# Anomaly Service

Anomaly Service is a rule-based Kafka worker. It consumes cleaned telemetry and
DLQ events, detects operational issues, and emits alert events for admin and
monitoring flows.

## Responsibilities

- Consume enriched GPS from `transport-telemetry-cleaned`.
- Consume rejected GPS envelopes from `transport-telemetry-dlq`.
- Maintain a sliding window of GPS pings to extract summary behavior vectors.
- Detect spatial anomalies using Isolation Forests (Erratic Driving) and DBSCAN spatial clustering (Stationary/Breakdowns).
- Publish alerts using **Audience Targeting** (Admin, Driver, Passenger) to ensure secure delivery.
- Expose health and Prometheus-style metrics on port `8006`.

## Kafka Topics

| Topic | Direction | Purpose |
|---|---|---|
| `transport-telemetry-cleaned` | consume | enriched GPS from Flink |
| `transport-telemetry-dlq` | consume | rejected GPS from ingestion |
| `transport-anomaly-alerts` | produce | alerts for admin/API/monitoring |

## Current Rules

| Rule | Meaning |
|---|---|
| `UNREALISTIC_SPEED` | speed is above safe threshold |
| `ERRATIC_DRIVING` | IsolationForest output `-1` on the window summary vector (Admin) |
| `OFF_ROUTE` | bus is too far from assigned route geometry (Admin, Driver) |
| `STATIONARY` | bus stopped for 5 minutes outside a DBSCAN spatial cluster (Driver) |
| `COMMUNICATION_LOSS` | active bus stops sending telemetry |
| `TRIP_NOT_STARTED_DEVICE_ACTIVE` | repeated `INACTIVE_TRIP` DLQ events for same bus |

The inactive-trip rule is useful when a device is powered on and sending GPS,
but the driver has not started the trip in Fleet.

## HTTP / Prometheus

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | service health summary |
| `GET` | `/health/live` | liveness |
| `GET` | `/health/ready` | readiness |
| `GET` | `/metrics` | Prometheus-style metrics |

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `KAFKA_CLEANED_TOPIC` | `transport-telemetry-cleaned` | cleaned telemetry source |
| `KAFKA_DLQ_TOPIC` | `transport-telemetry-dlq` | ingestion DLQ source |
| `KAFKA_ANOMALY_TOPIC` | `transport-anomaly-alerts` | alert output topic |
| `KAFKA_DLQ_GROUP_ID` | `anomaly-service-dlq-group` | DLQ consumer group |
| `ROUTE_SERVICE_URL` | `http://route-service:8002` | route geometry API |
| `COMMUNICATION_LOSS_CHECK_INTERVAL_SECONDS` | `60` | communication-loss scan interval |
| `COMMUNICATION_LOSS_THRESHOLD_SECONDS` | `180` | no-telemetry threshold |
| `INACTIVE_TRIP_DLQ_THRESHOLD_COUNT` | `3` | repeated inactive trip event count |
| `INACTIVE_TRIP_DLQ_WINDOW_SECONDS` | `60` | inactive trip window |
| `INACTIVE_TRIP_DLQ_COOLDOWN_SECONDS` | `300` | duplicate alert cooldown |

## MQTT / Redis

Anomaly Service does not subscribe to MQTT and does not use Redis directly.

## Cross-Group Notes

- This is rule-based, not ML/AI, in the current implementation.
- Alert read APIs for UI/admin are still a separate gateway/product concern.
- G4 should deploy the service privately and scrape `/metrics` internally.
