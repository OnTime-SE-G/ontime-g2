# G2 Services

This folder contains the deployable microservices and runtime jobs owned by
Group 2. Public client traffic should enter through G4 Kong and then the G2 API
Gateway or WebSocket service. Kafka, MQTT, Redis, PostgreSQL, and InfluxDB are
internal data-plane dependencies unless explicitly exposed by G4 for deployment.

## Service Map

| Service | Runtime | Port | Public Through Kong | Main Dependencies |
|---|---:|---:|---|---|
| `api-gateway` | FastAPI | `8000` | yes, REST API | route-service, fleet-service, Redis |
| `websocket-service` | FastAPI WebSocket | `8004` | yes, `WS /v1/live` | Redis Pub/Sub |
| `route-service` | FastAPI | `8002` | indirectly through API Gateway | PostgreSQL/PostGIS |
| `fleet-management-service` | FastAPI | `8003` | indirectly through API Gateway | PostgreSQL, Kafka, route-service |
| `ingestion` | Python MQTT worker + FastAPI probes | `8001` | no, internal/probes only | MQTT broker, Kafka |
| `stream-processing` | PyFlink job | Flink UI `8081` | no | Kafka, route-service, Redis, InfluxDB |
| `anomaly-service` | Kafka worker + FastAPI probes | `8006` | no direct public API | Kafka, route-service |
| `eta-service` | planned FastAPI + Kafka worker | TBD | through API Gateway when implemented | Kafka, Redis, InfluxDB |
| `auth-service` | planned/temporary Auth wrapper | planned `8005` | yes through Kong for auth routes | G4 Keycloak later |

## Shared Data Contracts

| Boundary | Contract |
|---|---|
| G1 GPS to G2 | MQTT `transport/bus/{busId}/location` |
| G1 heartbeat to G2 | MQTT `transport/bus/{busId}/heartbeat` |
| Fleet trip lifecycle | Kafka `trip.lifecycle` |
| Accepted GPS | Kafka `transport-telemetry-raw` |
| Rejected GPS | Kafka `transport-telemetry-dlq` |
| Enriched GPS | Kafka `transport-telemetry-cleaned` |
| Anomaly alerts | Kafka `transport-anomaly-alerts` |
| Live fleet updates | Redis Pub/Sub `fleet:live` |
| ETA live updates | Redis Pub/Sub `eta:live` |
| Latest bus snapshot | Redis key `bus:{busId}:position` |

## Operations Contract

Services with HTTP probes should expose:

| Endpoint | Purpose |
|---|---|
| `/health` | dependency-aware summary when implemented |
| `/health/live` | liveness probe when implemented |
| `/health/ready` | readiness probe when implemented |
| `/metrics` | Prometheus scrape endpoint when implemented |

Prometheus/G4 should scrape service endpoints internally in Kubernetes. These
operations endpoints should not be exposed as public passenger APIs.

## Cross-Group Rule

- G1 only needs the MQTT broker address, credentials, and publish topics.
- G3 only needs REST/WebSocket APIs exposed through G4/Kong.
- G4 needs image names, ports, probes, metrics, env vars, secrets, and internal
  dependency names.
- Kafka topic names are internal G2 contracts but G4 may need them for topic
  provisioning, ACLs, and deployment configuration.
