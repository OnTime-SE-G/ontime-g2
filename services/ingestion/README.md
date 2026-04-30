# Ingestion Service

The ingestion service is G2's MQTT-to-Kafka gateway. It accepts GPS telemetry from G1, validates it against the shared `GPSMessage` contract, applies stateful filtering, and forwards clean data to Kafka for downstream stream processing.

## What Phase 7 Completes

- packages runtime code under `services/ingestion/app/`
- adds a Docker image entrypoint for the full worker
- integrates `ingestion-service` into `docker/docker-compose.yml`
- exposes liveness and readiness probes for operations
- documents the G1 and G4 integration interfaces clearly

## Runtime Flow

```text
G1 GPS device / simulator
  -> MQTT broker (Mosquitto)
  -> ingestion-service
     -> schema validation
     -> geo validation
     -> duplicate / rate / sequence checks
     -> valid message -> Kafka raw topic
     -> invalid message -> Kafka DLQ topic
```

## Directory Layout

```text
services/ingestion/
  app/
    config.py
    health.py
    main.py
    metrics.py
    mqtt_subscriber.py
    producer.py
    validator.py
  tests/
  Dockerfile
  requirements.txt
  README.md
```

## Responsibilities

- subscribe to MQTT topic `transport/bus/+/location`
- validate JSON and `GPSMessage` schema
- reject coordinates outside Sri Lanka bounds
- detect duplicates from the same bus
- enforce minimum message interval per bus
- reject out-of-order timestamps per bus
- publish valid messages to Kafka topic `transport-telemetry-raw`
- publish invalid messages to Kafka topic `transport-telemetry-dlq`
- expose `/health`, `/health/live`, `/health/ready`, and `/metrics`

## Interfaces

### G1 -> G2 ingestion interface

| Item | Value |
|------|-------|
| Producer group | G1 Device & Edge |
| Protocol | MQTT 3.1.1 |
| Transport | Mosquitto broker |
| Topic | `transport/bus/{busId}/location` |
| Payload contract | `schemas/gps.py::GPSMessage` |
| Expected publish cadence | every 3 to 5 seconds per active bus |
| Current dev publisher | `scripts/gps_simulator.py` |

Required payload fields:

- `busId`
- `tripId`
- `lat`
- `lon`
- `speed`
- `heading`
- `timestamp`

### G2 ingestion -> downstream G2 interface

| Item | Value |
|------|-------|
| Consumer | stream-processing / downstream Kafka consumers |
| Protocol | Kafka |
| Valid topic | `transport-telemetry-raw` |
| Invalid topic | `transport-telemetry-dlq` |
| Keying | valid messages keyed by `busId` |

DLQ envelope includes:

- original payload
- error reason
- error type
- source
- source topic
- received timestamp

### G4 -> G2 ingestion interface

| Item | Value |
|------|-------|
| Consumer group | G4 Platform, Security & Integration |
| Access method | Docker Compose / container runtime / HTTP scrape |
| Health summary | `GET /health` |
| Liveness probe | `GET /health/live` |
| Readiness probe | `GET /health/ready` |
| Metrics scrape | `GET /metrics` |
| Default service port | `8001` |

G4 uses these interfaces for:

- container health monitoring
- orchestrator readiness checks
- Prometheus scraping
- debugging dependency failures

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER_HOST` | `mqtt-broker` | MQTT broker host |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC_PATTERN` | `transport/bus/+/location` | MQTT subscription pattern |
| `KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `INGESTION_KAFKA_RAW_TOPIC` | `transport-telemetry-raw` | topic for accepted telemetry |
| `INGESTION_KAFKA_DLQ_TOPIC` | `transport-telemetry-dlq` | topic for rejected telemetry |
| `INGESTION_SERVICE_PORT` | `8001` | port used by health and metrics server |
| `INGESTION_MIN_MESSAGE_INTERVAL_SECONDS` | `1.0` | minimum accepted gap between messages from the same bus |
| `INGESTION_DUPLICATE_CACHE_SIZE` | `100` | duplicate hash window per bus |

## Local Run

From the repo root:

```bash
python -m pip install -r services/ingestion/requirements.txt
python -m services.ingestion.app.main
```

## Docker Compose Run

From the repo root:

```bash
docker compose -f docker/docker-compose.yml up -d broker mqtt-broker ingestion-service
```

Useful checks:

```bash
curl http://localhost:8001/health
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready
curl http://localhost:8001/metrics
```

## Phase 7 Validation Checklist

- `docker compose` includes `ingestion-service`
- image starts with `python -m services.ingestion.app.main`
- readiness endpoint returns `200` only when Kafka and MQTT are connected
- liveness endpoint stays available while the service process is alive
- ingestion tests pass locally
- docs describe G1 and G4 integration points

## Tests

```bash
python -m pytest services/ingestion/tests -v
pytest services/ingestion/tests -v
```

## Important Notes

- The service is intentionally narrow in scope. It does not calculate ETA, render maps, or own user-facing APIs.
- `services/ingestion/app/` is the runtime package. Tests stay under `services/ingestion/tests/`.
- `services/ingestion/tests/conftest.py` is only a pytest path helper for this service's tests. It is not part of the runtime.

## Ownership

- Owner: Janidu
- Downstream reviewer: Natasha
- Infrastructure reviewer: Kusal
