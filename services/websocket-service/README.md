# WebSocket Service

WebSocket Service is the live push gateway for G3. It subscribes to Redis
Pub/Sub channels and broadcasts messages to connected clients.

## Responsibilities

- Accept WebSocket clients at `/v1/live`.
- Subscribe to Redis Pub/Sub `fleet:live` and `eta:live`.
- Broadcast live bus and ETA messages to all connected clients.
- Optionally filter initial state by `routeId` and `busId` query params.
- Expose health, readiness, and Prometheus-style metrics.

## Public WebSocket Contract

Clients connect through G4/Kong:

```text
WS /v1/live
WS /v1/live?routeId=202
WS /v1/live?busId=1
```

Current service broadcasts every Redis message it receives from the configured
channels. G4 should support WebSocket upgrade/proxying for this route.

## Redis Channels

| Channel | Producer | Payload |
|---|---|---|
| `fleet:live` | Flink | enriched live bus GPS |
| `eta:live` | planned ETA Service | ETA update events |

## HTTP / Prometheus

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Redis-aware health |
| `GET` | `/health/live` | liveness |
| `GET` | `/health/ready` | readiness |
| `GET` | `/metrics` | Prometheus-style metrics |
| `GET` | `/debug` | local debug only; do not expose publicly |

## Environment Variables

| Variable | Default | Meaning |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379` | Redis connection |
| `FLEET_CHANNEL` | `fleet:live` | live bus Redis channel |
| `ETA_CHANNEL` | `eta:live` | live ETA Redis channel |

## Kafka / MQTT

WebSocket Service does not consume Kafka or MQTT. Kafka/Flink/ETA publish into
Redis first; this service only handles client push.

## G4 / Kong Notes

- Expose `/v1/live` as a WebSocket route.
- Keep `/debug` internal or disabled in production.
- Passenger live tracking is public for current scope, with Kong rate and
  connection limits.
