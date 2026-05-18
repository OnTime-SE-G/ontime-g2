# Anomaly Service (CR2)

Anomaly Service is the core behavioral analysis worker. It consumes enriched GPS telemetry from `transport-telemetry-cleaned` and applies a combination of Machine Learning (Isolation Forests), Spatial Clustering (DBSCAN), and rigid rules to detect operational issues.

## Responsibilities

- **Stream Consumption**: Ingests enriched GPS from Flink and rejected envelopes from the Dead Letter Queue.
- **Behavioral ML**: Runs a pre-trained `IsolationForest` model across a sliding window of historical pings to detect erratic driving behaviors.
- **Spatial Clustering**: Uses `DBSCAN` to accurately identify genuinely stationary buses while ignoring GPS multipath noise.
- **Audience-Targeted Alerting**: Emits alerts to Kafka (`transport-anomaly-alerts`) for history, and securely routes real-time alerts to distinct Redis channels (`anomaly:passenger`, `anomaly:driver`, `anomaly:admin`) based on configuration rules.

## Current Anomaly Detectors

| Anomaly Type | Detection Method | Description |
|---|---|---|
| `UNREALISTIC_SPEED` | Rule-based | Speed exceeds physical limitations. |
| `OFF_ROUTE` | Rule-based | Bus is too far from its assigned geometry line. |
| `PERSISTENT_OFF_ROUTE` | Rule-based (Stateful) | 3-ping streak logic confirming persistent off-route deviation. |
| `STATIONARY` | ML (DBSCAN) | Bus remains clustered in a tight 50m radius for >5 minutes. |
| `ERRATIC_DRIVING` | ML (IsolationForest) | Detects anomalous multi-variate sliding windows (heading, speed). |
| `COMMUNICATION_LOSS` | Timer-based | Active bus stops sending telemetry for >3 minutes. |
| `TRIP_NOT_STARTED_DEVICE_ACTIVE` | DLQ Analysis | Repeated `INACTIVE_TRIP` DLQ events for an powered-on bus. |

## Targeted Live Channels (WebSockets)

Alerts are pushed live to Redis so the WebSocket Service can stream them to the UI. The audience routing is fully configurable.

| Target Audience | Default Redis Channel | Config Variable | Default Anomalies |
|---|---|---|---|
| Passenger | `anomaly:passenger` | `ANOMALY_REDIS_PASSENGER_CHANNEL` | `STATIONARY` |
| Driver | `anomaly:driver` | `ANOMALY_REDIS_DRIVER_CHANNEL` | `OFF_ROUTE`, `STATIONARY`, `UNREALISTIC_SPEED` |
| Admin | `anomaly:admin` | `ANOMALY_REDIS_ADMIN_CHANNEL` | All Anomalies (Fallback) |

## HTTP / Prometheus

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service health, ML model loading status |
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe |
| `GET` | `/metrics` | Prometheus-style metrics |

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `KAFKA_CLEANED_TOPIC` | `transport-telemetry-cleaned` | Cleaned telemetry source |
| `KAFKA_DLQ_TOPIC` | `transport-telemetry-dlq` | Ingestion DLQ source |
| `KAFKA_ANOMALY_TOPIC` | `transport-anomaly-alerts` | Alert output topic |
| `ROUTE_SERVICE_URL` | `http://route-service:8002` | Route geometry API |
| `REDIS_HOST` | `redis` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `ANOMALY_ADMIN_TYPES` | `...` | Comma-separated list of admin alerts |
