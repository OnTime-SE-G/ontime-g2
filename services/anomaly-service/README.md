# Anomaly Service

Anomaly Service is the G2 operational-alert worker. It consumes Flink-enriched
telemetry and ingestion DLQ events, detects unsafe or suspicious bus behavior,
and publishes alert events for operations, admin, and live WebSocket flows.

## Responsibilities

- Consume enriched GPS from Kafka `transport-telemetry-cleaned`.
- Consume rejected GPS envelopes from Kafka `transport-telemetry-dlq`.
- Load route geometries from Route Service for local off-route checks.
- Detect rule-based operational anomalies.
- Detect erratic driving with an Isolation Forest over sliding-window summary
  features when the model artifact is available.
- Publish alerts to Kafka `transport-anomaly-alerts`.
- Publish live alerts to Redis Pub/Sub `anomaly:live`.
- Persist alert records to PostgreSQL `anomaly_db`.
- Expose health and Prometheus-style metrics on port `8006`.

## Runtime Flow

```text
Flink cleaned telemetry
  -> Kafka transport-telemetry-cleaned
  -> Anomaly Service
  -> Kafka transport-anomaly-alerts
  -> Redis anomaly:live
  -> PostgreSQL anomaly_alerts

Ingestion DLQ
  -> Kafka transport-telemetry-dlq
  -> Anomaly Service inactive-trip analysis
```

## Kafka Topics

| Topic | Direction | Purpose |
|---|---|---|
| `transport-telemetry-cleaned` | consume | enriched GPS from Flink |
| `transport-telemetry-dlq` | consume | rejected GPS from ingestion |
| `transport-anomaly-alerts` | produce | anomaly alerts for admin/API/monitoring |

## Redis

| Channel | Direction | Purpose |
|---|---|---|
| `anomaly:live` | produce | live anomaly alerts for WebSocket fan-out |

## Current Detectors

| Alert type | Method | Meaning |
|---|---|---|
| `UNREALISTIC_SPEED` | Rule | speed exceeds the safe threshold |
| `INACTIVE_GPS` | Rule | telemetry has no active `routeId` context |
| `OFF_ROUTE` | Rule | bus is too far from its assigned route geometry |
| `PERSISTENT_OFF_ROUTE` | Stateful rule | repeated off-route readings inside the configured window |
| `STATIONARY` | Stateful rule | bus remains nearly stopped for more than 5 minutes |
| `COMMUNICATION_LOSS` | Timer rule | active bus stops sending telemetry |
| `TRIP_NOT_STARTED_DEVICE_ACTIVE` | DLQ analysis | repeated `INACTIVE_TRIP` DLQ events for the same bus |
| `ERRATIC_DRIVING` | Isolation Forest or fallback rules | sliding-window speed/heading behavior looks anomalous |

The inactive-trip detector is useful when a device is powered on and sending
GPS, but the driver has not started the trip in Fleet.

## Behavioral ML

The service keeps a recent telemetry window per bus. Once the configured
minimum window size is reached, it builds a summary vector with values such as:

- `max_acceleration`
- `min_acceleration`
- `speed_variance`
- `heading_variance`
- `average_speed`
- `sample_count`

If the Isolation Forest artifact loads successfully, the model predicts whether
that summary vector is normal or anomalous. If the model is unavailable, the
service uses configurable fallback thresholds for speed variance, heading
variance, and acceleration.

## HTTP / Prometheus

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | service health and Isolation Forest status |
| `GET` | `/health/live` | liveness |
| `GET` | `/health/ready` | readiness |
| `GET` | `/metrics` | Prometheus-style metrics |

## Environment Variables

`ANOMALY_` variables are preferred. Several legacy aliases are still accepted by
`app/config.py` for compatibility.

| Variable | Default | Meaning |
|---|---|---|
| `ANOMALY_SERVICE_PORT` | `8006` | health/metrics HTTP port |
| `ANOMALY_KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `ANOMALY_KAFKA_CLEANED_TOPIC` | `transport-telemetry-cleaned` | cleaned telemetry source |
| `ANOMALY_KAFKA_DLQ_TOPIC` | `transport-telemetry-dlq` | ingestion DLQ source |
| `ANOMALY_KAFKA_ALERTS_TOPIC` | `transport-anomaly-alerts` | alert output topic |
| `ANOMALY_KAFKA_CLEANED_GROUP_ID` | `anomaly-service-group` | cleaned telemetry consumer group |
| `ANOMALY_KAFKA_DLQ_GROUP_ID` | `anomaly-service-dlq-group` | DLQ consumer group |
| `ANOMALY_DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/anomaly_db` | alert storage database |
| `ANOMALY_REDIS_HOST` | `redis` | Redis host for live alerts |
| `ANOMALY_REDIS_PORT` | `6379` | Redis port for live alerts |
| `ANOMALY_REDIS_LIVE_CHANNEL` | `anomaly:live` | Redis Pub/Sub alert channel |
| `ANOMALY_ROUTE_SERVICE_URL` | `http://route-service:8002` | private Route Service URL |
| `ANOMALY_ROUTE_FETCH_TIMEOUT_SECONDS` | `10.0` | route geometry fetch timeout |
| `ANOMALY_ROUTE_REFRESH_INTERVAL_SECONDS` | `300` | route geometry refresh interval |
| `ANOMALY_COMMUNICATION_LOSS_CHECK_INTERVAL_SECONDS` | `60` | communication-loss scan interval |
| `ANOMALY_COMMUNICATION_LOSS_THRESHOLD_SECONDS` | `180` | no-telemetry threshold |
| `ANOMALY_INACTIVE_TRIP_DLQ_THRESHOLD_COUNT` | `3` | inactive-trip DLQ count before alerting |
| `ANOMALY_INACTIVE_TRIP_DLQ_WINDOW_SECONDS` | `60` | inactive-trip DLQ aggregation window |
| `ANOMALY_INACTIVE_TRIP_DLQ_COOLDOWN_SECONDS` | `300` | duplicate inactive-trip alert cooldown |
| `ANOMALY_OFF_ROUTE_DISTANCE_THRESHOLD_M` | `50.0` | distance from route before off-route alerting |
| `ANOMALY_OFF_ROUTE_STREAK_WINDOW_SECONDS` | `5` | off-route streak window |
| `ANOMALY_PERSISTENT_OFF_ROUTE_THRESHOLD` | `3` | readings before persistent off-route alert |
| `ANOMALY_SLIDING_WINDOW_SIZE` | `20` | telemetry samples used for behavioral features |
| `ANOMALY_SLIDING_WINDOW_MIN_SIZE` | `10` | minimum samples before behavioral inference |
| `ANOMALY_BEHAVIORAL_FALLBACK_SPEED_VARIANCE` | `8.0` | fallback speed variance threshold |
| `ANOMALY_BEHAVIORAL_FALLBACK_HEADING_VARIANCE` | `5.0` | fallback heading variance threshold |
| `ANOMALY_BEHAVIORAL_FALLBACK_MAX_ACCELERATION` | `3.0` | fallback acceleration threshold |
| `ANOMALY_ISOLATION_FOREST_ARTIFACT_PATH` | `app/models/training/isolation_forest.joblib` | local model artifact path |

## Run

Local Python:

```bash
python -m pip install -r services/anomaly-service/requirements.txt
cd services/anomaly-service
python -m app.main
```

Docker Compose:

```bash
docker compose -f docker/docker-compose.yml up -d anomaly-service
```

Useful checks:

```bash
curl http://localhost:8006/health
curl http://localhost:8006/health/live
curl http://localhost:8006/health/ready
curl http://localhost:8006/metrics
```

## Tests

```bash
cd services/anomaly-service
python -m pytest tests -v
```

The unit tests cover model rules, inactive-trip DLQ analysis, config loading,
and behavioral feature extraction.

## Cross-Group Notes

- G3 should consume live alert streams through the WebSocket route exposed by
  G4/Kong, not by connecting directly to Redis.
- G4 should deploy this service privately and scrape `/metrics` internally.
- Alert read/history APIs are a separate API Gateway/admin concern.
