# Stream Processing Service

The stream-processing service is a PyFlink job, not a normal REST service. It
reads raw GPS and trip lifecycle streams, enriches telemetry with route context,
writes live state to Redis, writes history to InfluxDB, and publishes cleaned
GPS for downstream services.

## Responsibilities

- Consume accepted GPS from Kafka `transport-telemetry-raw`.
- Consume trip lifecycle events from Kafka `trip.lifecycle`.
- Keep `tripId -> routeId` state from lifecycle events.
- Cache route geometries from Route Service at job startup.
- Drop late/duplicate/invalid telemetry.
- Add `routeId`, `routeProgressPct`, and remaining distance fields.
- Publish enriched GPS to Kafka `transport-telemetry-cleaned`.
- Write latest positions to Redis key `bus:{busId}:position`.
- Publish live fleet updates to Redis Pub/Sub `fleet:live`.
- Write historical GPS points to InfluxDB measurement `gps_readings`.

## Kafka Topics

| Topic | Direction | Purpose |
|---|---|---|
| `transport-telemetry-raw` | consume | active-trip GPS from ingestion |
| `trip.lifecycle` | consume | trip start/end context from Fleet |
| `transport-telemetry-cleaned` | produce | enriched GPS for ETA and Anomaly |

## Redis / Influx Outputs

| Output | Shape |
|---|---|
| Redis key | `bus:{busId}:position` stores latest enriched JSON |
| Redis Pub/Sub | `fleet:live` publishes enriched live bus JSON |
| InfluxDB | bucket `telemetry`, measurement `gps_readings` |

## HTTP / Prometheus

This service does not expose its own FastAPI endpoints. Operations visibility
comes from the Flink JobManager and task logs.

| Endpoint | Owner |
|---|---|
| Flink UI / jobs API `:8081` | Flink JobManager |
| App `/metrics` | not implemented |

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `KAFKA_RAW_TOPIC` | `transport-telemetry-raw` | raw GPS source |
| `KAFKA_CLEANED_TOPIC` | `transport-telemetry-cleaned` | enriched GPS sink |
| `KAFKA_LIFECYCLE_TOPIC` | `trip.lifecycle` | trip lifecycle source |
| `REDIS_HOST` | `redis` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `INFLUXDB_URL` | `http://influxdb:8086` | InfluxDB URL |
| `INFLUXDB_TOKEN` | `super_secret_admin_token_123` | InfluxDB token; use secret in deployment |
| `INFLUXDB_ORG` | `ontime` | InfluxDB org |
| `INFLUXDB_BUCKET` | `telemetry` | InfluxDB bucket |
| `ROUTE_SERVICE_URL` | `http://route-service:8002` | route geometry API |

## Output Message Example

```json
{
  "busId": "1",
  "tripId": "TRIP-001",
  "routeId": "202",
  "lat": 6.9271,
  "lon": 79.8612,
  "speed": 35.0,
  "heading": 120.0,
  "timestamp": "2026-05-02T10:15:30Z",
  "remainingDistanceToNextStops": 523.4,
  "routeProgressPct": 61.25
}
```

## Future ETA Feature Plan

The agreed ETA direction is that Flink should calculate ETA-ready route/stop
features and publish them to a dedicated ETA feature stream or enriched stream.
ETA Service should then compute ETA from those features without calling Route
Service for every request.
