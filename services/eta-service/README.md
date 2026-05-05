# ETA Service

ETA Service is currently a planned G2 service. It will compute estimated arrival
times from Flink-enriched live telemetry. The initial implementation should use
a deterministic physics model; later increments can add XGBoost or another ML
model with the physics model as fallback.

## Current Status

- No deployable ETA service code is on this branch yet.
- API Gateway ETA endpoints are planned, not currently implemented here.
- WebSocket Service already supports `eta:live`; it will broadcast ETA messages
  once ETA Service publishes to that Redis channel.

## Planned Responsibilities

- Consume ETA-ready telemetry from Kafka.
- Keep a latest snapshot per `tripId` in Redis.
- Compute ETA for `(tripId, stopId)`, not `(busId, stopId)`.
- Publish live ETA updates to Redis Pub/Sub `eta:live`.
- Optionally write ETA prediction history to InfluxDB.
- Serve on-demand REST ETA through API Gateway.

## Planned Kafka / Redis Contracts

| Contract | Direction | Purpose |
|---|---|---|
| `transport-telemetry-cleaned` | consume, current option | enriched GPS from Flink |
| `transport-eta-features` | consume, optional dedicated future topic | ETA-specific features from Flink |
| Redis key `eta:trip:{tripId}:snapshot` | write/read | latest ETA feature snapshot |
| Redis Pub/Sub `eta:live` | produce | live ETA push to WebSocket Service |

## Planned HTTP Contract

External clients should call through G4/Kong and G2 API Gateway:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/eta/{tripId}/{stopId}?model=physics` | on-demand ETA |

Internal ETA Service route can mirror:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/eta/{tripId}/{stopId}` | compute/read ETA from latest Redis snapshot |
| `GET` | `/health` | health |
| `GET` | `/health/live` | liveness |
| `GET` | `/health/ready` | readiness |
| `GET` | `/metrics` | Prometheus metrics |

## Planned Environment Variables

| Variable | Suggested Default | Meaning |
|---|---|---|
| `ETA_SERVICE_PORT` | `8007` | service port; avoid existing ports |
| `KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `KAFKA_ETA_FEATURE_TOPIC` | `transport-eta-features` | ETA feature source if dedicated topic is used |
| `KAFKA_CLEANED_TOPIC` | `transport-telemetry-cleaned` | source if reusing cleaned stream |
| `REDIS_URL` | `redis://redis:6379` | Redis snapshot and Pub/Sub |
| `ETA_LIVE_CHANNEL` | `eta:live` | Redis Pub/Sub channel |
| `INFLUXDB_URL` | `http://influxdb:8086` | optional ETA history store |
| `INFLUXDB_TOKEN` | secret | InfluxDB token |
| `INFLUXDB_ORG` | `ontime` | InfluxDB org |
| `INFLUXDB_BUCKET` | `eta_predictions` | ETA history bucket |

## ETA Message Example

```json
{
  "event": "eta_update",
  "tripId": "TRIP-001",
  "busId": "1",
  "routeId": "202",
  "stopId": 42,
  "eta_seconds": 120.5,
  "model_used": "physics",
  "distance_m": 234.5,
  "speed_ms": 1.95,
  "timestamp": "2026-05-05T01:00:00Z"
}
```

## Cross-Group Notes

- G3 should use API Gateway REST for on-demand ETA and `WS /v1/live` for live ETA.
- G4 should route public ETA reads through Kong/API Gateway, not directly to ETA Service.
- G2 should keep ETA Service private inside the cluster.
