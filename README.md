# OnTime G2 - Data, Intelligence, and Live Transport Backend

OnTime is a real-time public transport platform. This repository contains the
Group 2 backend services: ingestion, route/fleet data services, stream
processing, anomaly detection, live WebSocket push, and planned ETA/Auth
integration contracts.

## Group Boundaries

| Group | Owns | Interface With G2 |
|---|---|---|
| G1 | bus device firmware and GPS publisher | MQTT GPS + heartbeat topics |
| G2 | data services, stream processing, ETA/anomaly logic | this repo |
| G3 | passenger, driver, and admin UI | REST + WebSocket through G4/Kong |
| G4 | Kubernetes, Kong, auth, monitoring, deployment | Docker images, probes, metrics, env/secrets |

Important: Kafka, Redis, PostgreSQL, InfluxDB, and most service-to-service HTTP
calls are internal G2 data-plane contracts. G4 needs them for deployment and
provisioning, but G3 should not call them directly.

## Current Architecture

```mermaid
flowchart LR
  G1["G1 Bus Device"] -->|"MQTT transport/bus/{busId}/location"| MQTT["MQTT Broker"]
  G1 -->|"MQTT transport/bus/{busId}/heartbeat"| MQTT

  G3["G3 UI"] -->|"REST + WebSocket"| KONG["G4 Kong + Auth"]
  KONG -->|"REST /api/v1/*"| APIGW["G2 API Gateway"]
  KONG -->|"WS /v1/live"| WS["WebSocket Service"]
  G4MON["G4 Prometheus / K8s"] -->|"/health, /ready, /metrics"| OPS["G2 service probes"]

  APIGW --> ROUTE["Route Service"]
  APIGW --> FLEET["Fleet Management Service"]
  APIGW --> REDIS["Redis"]
  APIGW -. planned .-> ETA["ETA Service"]
  APIGW -. planned .-> AUTH["Auth Wrapper Contract"]

  ROUTE --> PG["PostgreSQL / PostGIS"]
  FLEET --> PG
  FLEET -->|"Kafka trip.lifecycle"| KAFKA["Kafka / AutoMQ-compatible Broker"]

  MQTT --> ING["Ingestion Service"]
  KAFKA -->|"trip.lifecycle"| ING
  ING -->|"transport-telemetry-raw"| KAFKA
  ING -->|"transport-telemetry-dlq"| KAFKA

  KAFKA -->|"raw GPS + lifecycle"| FLINK["PyFlink Stream Processing"]
  ROUTE -->|"/internal/routes/geometry"| FLINK
  FLINK -->|"transport-telemetry-cleaned"| KAFKA
  FLINK -->|"bus:{busId}:position"| REDIS
  FLINK -->|"fleet:live"| REDIS
  FLINK -->|"gps_readings"| INFLUX["InfluxDB"]

  KAFKA -->|"transport-telemetry-cleaned + dlq"| ANOM["Anomaly Service"]
  ROUTE -->|"/internal/routes/geometry"| ANOM
  ANOM -->|"transport-anomaly-alerts"| KAFKA

  KAFKA -. planned ETA features .-> ETA
  ETA -. planned .->|"eta:live"| REDIS
  ETA -. planned .-> INFLUX

  REDIS -->|"fleet:live + eta:live"| WS
```

## Deployable Services

| Service | Folder | Port | Public? | Notes |
|---|---|---:|---|---|
| API Gateway | `services/api-gateway` | `8000` | yes, through Kong | G3 REST facade |
| WebSocket Service | `services/websocket-service` | `8004` | yes, through Kong | `WS /v1/live` |
| Route Service | `services/route-service` | `8002` | no direct public access | route/stop/PostGIS owner |
| Fleet Management Service | `services/fleet-management-service` | `8003` | no direct public access | buses, drivers, schedules, trips |
| Ingestion Service | `services/ingestion` | `8001` | no direct public access | MQTT to Kafka boundary |
| Stream Processing | `services/stream-processing` | Flink UI `8081` | no | PyFlink job |
| Anomaly Service | `services/anomaly-service` | `8006` | no direct public access | Kafka alert worker |
| ETA Service | `services/eta-service` | planned `8007` | through API Gateway later | planned |
| Auth Wrapper | `services/auth-service` | planned `8005` | through Kong/Auth | temporary contract only |

## Public API Surface For G3

G3 should call these through G4 Kong. Kong applies auth/RBAC before forwarding to
G2.

### Passenger / Public Current Scope

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/status` | API Gateway status |
| `GET` | `/api/v1/routes` | list routes |
| `GET` | `/api/v1/routes/search` | search routes |
| `GET` | `/api/v1/routes/{route_id}` | route detail |
| `GET` | `/api/v1/routes/{route_id}/transit-data` | route aggregate |
| `GET` | `/api/v1/routes/all-transit-data` | all transit aggregate |
| `GET` | `/api/v1/routes/{route_id}/stops` | stops on route |
| `GET` | `/api/v1/routes/{route_id}/buses` | buses on route |
| `GET` | `/api/v1/routes/{route_id}/progress` | progress for a GPS point |
| `GET` | `/api/v1/stops` | all stops |
| `GET` | `/api/v1/stops/nearby` | nearby stops |
| `GET` | `/api/v1/stops/{stop_id}/routes` | routes serving stop |
| `GET` | `/api/v1/buses/live` | latest live bus snapshots |
| `GET` | `/api/v1/buses/route/{route_id}` | buses on route |
| `GET` | `/api/v1/buses/{bus_id}` | bus detail |
| `GET` | `/api/v1/trips/{trip_id}/state` | trip state |
| `WS` | `/v1/live` | live bus and ETA push |

### Driver - Requires `DRIVER`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/driver/trips/today` | driver planned trips |
| `POST` | `/api/v1/driver/trips/{trip_id}/start` | start trip |
| `POST` | `/api/v1/driver/trips/{trip_id}/end` | end trip |
| `POST` | `/api/v1/driver/trips/{trip_id}/report-delay` | report delay |
| `POST` | `/api/v1/driver/trips/{trip_id}/report-incident` | report incident |

### Admin - Requires `ADMIN`

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/admin/routes/add-route` | import route |
| `PUT` | `/api/v1/admin/routes/{route_id}` | replace route |
| `DELETE` | `/api/v1/admin/routes/{route_id}` | delete route |
| `POST` | `/api/v1/admin/fleet/buses` | create bus |
| `PUT` | `/api/v1/admin/fleet/buses/{bus_id}` | update bus |
| `DELETE` | `/api/v1/admin/fleet/buses/{bus_id}` | delete bus |
| `GET` | `/api/v1/admin/fleet/buses` | list buses |
| `GET` | `/api/v1/admin/fleet/buses/{bus_id}` | bus detail |
| `POST` | `/api/v1/admin/fleet/buses/{bus_id}/assign-route/{route_id}` | assign bus route through gateway |
| `POST` | `/api/v1/admin/fleet/buses/{bus_id}/unassign` | unassign bus route through gateway |
| `POST` | `/api/v1/admin/fleet/drivers` | create driver profile; Auth linking planned |
| `GET` | `/api/v1/admin/fleet/drivers` | list drivers |
| `POST` | `/api/v1/admin/fleet/schedules` | create schedule |
| `GET` | `/api/v1/admin/fleet/schedules` | list schedules |
| `POST` | `/api/v1/admin/fleet/planned-trips/generate` | generate daily trips |
| `GET` | `/api/v1/admin/fleet/planned-trips/today` | today's planned trips |
| `GET` | `/api/v1/admin/fleet/planned-trips/{trip_id}` | trip detail |
| `PATCH` | `/api/v1/admin/fleet/planned-trips/{trip_id}/assign` | assign bus/driver |
| `POST` | `/api/v1/admin/fleet/planned-trips/{trip_id}/delay` | admin delay update |
| `POST` | `/api/v1/admin/fleet/planned-trips/{trip_id}/incident` | admin incident update |

### Planned Auth And ETA

| Contract | Planned Path | Notes |
|---|---|---|
| Login | `POST /auth/login` | G4 Keycloak/Auth owner |
| Admin creates auth user | `POST /auth/admin/users` | `ADMIN` only |
| Disable auth user | `PATCH /auth/admin/users/{authUserId}/disable` | `ADMIN` only |
| Driver first password reset | `PATCH /auth/users/{authUserId}/change-password` | Auth-owned |
| On-demand ETA | `GET /api/v1/eta/{tripId}/{stopId}` | planned, trip-scoped |

## G1 MQTT Contract

| Purpose | Topic | Retain |
|---|---|---|
| live GPS | `transport/bus/{busId}/location` | `false` |
| heartbeat/device status | `transport/bus/{busId}/heartbeat` | allowed if timestamped |

GPS payload from G1 must not include `tripId`; ingestion enriches it from
Fleet's `trip.lifecycle` stream.

```json
{
  "busId": "1",
  "lat": 6.9271,
  "lon": 79.8612,
  "speed": 35.0,
  "heading": 120.0,
  "timestamp": "2026-05-02T10:15:30Z"
}
```

Heartbeat is metrics/device-status only and is not sent to raw telemetry Kafka.

## Kafka Topics

| Topic | Producer | Consumer | Purpose |
|---|---|---|---|
| `trip.lifecycle` | Fleet Management | Ingestion, Flink | trip start/end state |
| `transport-telemetry-raw` | Ingestion | Flink | accepted active-trip GPS |
| `transport-telemetry-dlq` | Ingestion | Anomaly, operators | rejected GPS envelope |
| `transport-telemetry-cleaned` | Flink | Anomaly, planned ETA | enriched GPS |
| `transport-anomaly-alerts` | Anomaly Service | planned API/admin readers | alert events |
| `transport-eta-features` | planned Flink | planned ETA Service | optional ETA feature stream |

## Redis Channels And Keys

| Name | Type | Producer | Consumer |
|---|---|---|---|
| `fleet:live` | Pub/Sub channel | Flink | WebSocket Service |
| `eta:live` | Pub/Sub channel | planned ETA Service | WebSocket Service |
| `bus:{busId}:position` | key | Flink | API Gateway, WebSocket initial state |
| `eta:trip:{tripId}:snapshot` | planned key | ETA Service | ETA Service |

## Operations For G4

G4 should use Kubernetes probes and Prometheus scraping internally. These routes
should not be exposed as passenger/admin APIs unless explicitly needed.

| Service | Health / Probes | Metrics |
|---|---|---|
| API Gateway | `/health` | `/metrics` |
| WebSocket Service | `/health`, `/health/live`, `/health/ready` | `/metrics` |
| Fleet Management | `/health`, `/health/live`, `/health/ready` | `/metrics` |
| Ingestion | `/health`, `/health/live`, `/health/ready` | `/metrics` |
| Anomaly Service | `/health`, `/health/live`, `/health/ready` | `/metrics` |
| Route Service | `/health` | not implemented yet |
| Stream Processing | Flink JobManager health/jobs | Flink runtime metrics |
| ETA/Auth | planned | planned |

## Core Environment Variables

Detailed env tables live in each service README.

| Service | Important Vars |
|---|---|
| API Gateway | `ROUTE_SERVICE_URL`, `FLEET_SERVICE_URL`, `REDIS_URL`, planned `AUTH_SERVICE_URL` |
| Route Service | `DATABASE_URL` |
| Fleet Management | `DATABASE_URL`, `KAFKA_BROKER_URL`, `KAFKA_TRIP_LIFECYCLE_TOPIC`, `ROUTE_SERVICE_URL` |
| Ingestion | `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TLS_ENABLED`, `KAFKA_BROKER_URL`, `INGESTION_KAFKA_RAW_TOPIC`, `INGESTION_KAFKA_DLQ_TOPIC`, `INGESTION_KAFKA_TRIP_LIFECYCLE_TOPIC` |
| Stream Processing | `KAFKA_BROKER_URL`, `KAFKA_RAW_TOPIC`, `KAFKA_CLEANED_TOPIC`, `KAFKA_LIFECYCLE_TOPIC`, `REDIS_HOST`, `REDIS_PORT`, `INFLUXDB_URL`, `ROUTE_SERVICE_URL` |
| WebSocket Service | `REDIS_URL`, `FLEET_CHANNEL`, `ETA_CHANNEL` |
| Anomaly Service | `KAFKA_BROKER_URL`, `KAFKA_CLEANED_TOPIC`, `KAFKA_DLQ_TOPIC`, `KAFKA_ANOMALY_TOPIC`, `ROUTE_SERVICE_URL` |
| ETA Service | planned `KAFKA_ETA_FEATURE_TOPIC`, `REDIS_URL`, `ETA_LIVE_CHANNEL`, `INFLUXDB_*` |
| Auth Wrapper | planned `AUTH_BOOTSTRAP_ADMIN_*`, `AUTH_TOKEN_SECRET` |

## Local Docker Compose

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

Common local checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health/ready
curl http://localhost:8003/health/ready
curl http://localhost:8004/health/ready
curl http://localhost:8006/health/ready
```

Kafka topic initialization is handled by `kafka-init` in compose.

## Test Commands

```bash
python -m pytest tests/unit -q
python -m pytest services/ingestion/tests/unit -q
python -m pytest services/api-gateway/tests/unit -q
python -m pytest services/fleet-management-service/tests/unit -q
python -m pytest services/stream-processing/tests/unit -q
python -m pytest services/anomaly-service/tests/unit -q
```

Live pipeline smoke test, when Docker is available:

```bash
python -m pytest tests/integration/test_live_pipeline_smoke.py -m integration -v -s
```

## Documentation Index

| Document | Purpose |
|---|---|
| `services/api-gateway/README.md` | REST facade endpoints and env vars |
| `services/ingestion/README.md` | MQTT/Kafka ingestion contract |
| `services/stream-processing/README.md` | Flink sources/sinks and Redis/Influx outputs |
| `services/fleet-management-service/README.md` | fleet/trip lifecycle APIs and Kafka event |
| `services/route-service/README.md` | route/stop/internal geometry APIs |
| `services/websocket-service/README.md` | WebSocket and Redis Pub/Sub contract |
| `services/anomaly-service/README.md` | anomaly topics, rules, probes |
| `services/eta-service/README.md` | planned ETA contracts |
| `services/auth-service/README.md` | G2/G4 auth boundary |
