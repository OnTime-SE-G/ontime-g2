# Ingestion Service

The ingestion service is G2's MQTT-to-Kafka boundary for live bus telemetry. It
receives GPS from G1, validates the payload, checks that the bus has an active
Fleet trip, enriches accepted GPS with `tripId`, and publishes clean telemetry
to Kafka. Bad GPS goes to the DLQ with typed reasons and useful metadata.

## End-to-End Flow

```text
Fleet start trip
  -> Kafka trip.lifecycle
  -> ingestion active-trip cache

G1 GPS device
  -> MQTT transport/bus/{busId}/location
  -> ingestion schema/geo/trip/event-time validation
  -> Kafka transport-telemetry-raw
  -> stream processing / live map

Invalid or inactive GPS
  -> Kafka transport-telemetry-dlq

G1 heartbeat
  -> MQTT transport/bus/{busId}/heartbeat
  -> ingestion metrics only
```

## Contracts

### MQTT Topics

| Purpose | G1 publish topic | Ingestion subscribe pattern | Retained |
|---------|------------------|-----------------------------|----------|
| Live GPS | `transport/bus/{busId}/location` | `transport/bus/+/location` | `false` |
| Device heartbeat | `transport/bus/{busId}/heartbeat` | `transport/bus/+/heartbeat` | allowed if timestamped |

G1 GPS payload:

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

Rules:

- `busId` is the Fleet bus id serialized as a string.
- G1 does not send `tripId`; ingestion adds it from `trip.lifecycle`.
- `timestamp` is required ISO 8601 UTC event time.
- `speed` is km/h.
- `heading` is degrees from `0` to `360`.
- live GPS must not be retained, because retained GPS can replay stale movement.

Heartbeat payload:

```json
{
  "busId": "1",
  "deviceId": "GPS-1",
  "timestamp": "2026-05-02T10:15:30Z",
  "gpsFix": true,
  "satellites": 8,
  "signalQuality": 21,
  "batteryVoltage": 3.9,
  "firmwareVersion": "g1-0.1.0"
}
```

Heartbeat is device status only. It is not published to
`transport-telemetry-raw`.

### Kafka Topics

| Topic | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `trip.lifecycle` | Fleet Management | ingestion, stream processing | active trip start/end events |
| `transport-telemetry-raw` | ingestion | stream processing | accepted active-trip GPS |
| `transport-telemetry-dlq` | ingestion | operators/anomaly tooling | rejected GPS with reason metadata |

Trip lifecycle start event:

```json
{
  "event": "TRIP_STARTED",
  "busId": "1",
  "tripId": "TRIP-001",
  "routeId": "202",
  "timestamp": "2026-05-02T10:00:00Z"
}
```

`TRIP_ENDED` with the same `busId` and `tripId` removes the bus from the active
trip cache.

Accepted raw Kafka GPS after ingestion enrichment:

```json
{
  "busId": "1",
  "tripId": "TRIP-001",
  "lat": 6.9271,
  "lon": 79.8612,
  "speed": 35.0,
  "heading": 120.0,
  "timestamp": "2026-05-02T10:15:30Z"
}
```

DLQ envelope includes:

- `original_payload`
- `busId` if parseable from payload or topic
- `tripId` if parseable from payload
- `event_timestamp` if parseable from payload
- `error_type`
- `error_reason`
- `source`
- `source_topic`
- `received_at`

Current GPS rejection reasons:

`JSON_PARSE`, `MISSING_TIMESTAMP`, `SCHEMA_VALIDATION`, `GEO_BOUNDS`,
`INACTIVE_TRIP`, `TRIP_CACHE_REBUILDING`, `DUPLICATE`,
`RATE_LIMIT`, `RATE_LIMIT_EVENT_TIME`, `SEQUENCE_ERROR`,
`FUTURE_TIMESTAMP`, `STALE_REPLAY`.

## HTTP Endpoints

| Endpoint | Meaning |
|----------|---------|
| `GET /health` | dependency-aware service summary |
| `GET /health/live` | process liveness |
| `GET /health/ready` | readiness for Kafka, MQTT, and trip-cache state |
| `GET /metrics` | Prometheus-style counters and gauges |

Readiness returns `200` only when Kafka is up, MQTT is up, and the active-trip
cache is ready when `INGESTION_REQUIRE_ACTIVE_TRIP=true`.

## Validation Rules

Ingestion accepts a GPS message only when all checks pass:

1. payload is UTF-8 JSON object
2. required `timestamp` exists
3. payload matches `GPSLocationMessage`
4. coordinates are inside Sri Lanka bounds
5. cache is ready, or the message is buffered during startup rebuild
6. bus has an active trip in the local cache
7. enriched GPS passes future/stale, duplicate, sequence, and event-time interval checks

Event-time defaults:

| Variable | Default | Meaning |
|----------|---------|---------|
| `INGESTION_MIN_EVENT_INTERVAL_SECONDS` | `1.0` | minimum event-time gap per bus |
| `INGESTION_MAX_FUTURE_SKEW_SECONDS` | `30.0` | allowed future clock skew |
| `INGESTION_MAX_STALE_AGE_SECONDS` | `86400.0` | allowed stale replay age |
| `INGESTION_DUPLICATE_CACHE_SIZE` | `100` | recent payload hashes per bus |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER_HOST` | `mqtt-broker` | MQTT broker host |
| `MQTT_BROKER_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC_PATTERN` | `transport/bus/+/location` | GPS subscription pattern |
| `MQTT_HEARTBEAT_TOPIC_PATTERN` | `transport/bus/+/heartbeat` | heartbeat subscription pattern |
| `MQTT_TLS_ENABLED` | `false` | enable TLS for secured brokers |
| `MQTT_USERNAME` | unset | optional MQTT username |
| `MQTT_PASSWORD` | unset | optional MQTT password |
| `MQTT_CLIENT_ID` | `ontime-ingestion-service` | MQTT client id |
| `MQTT_CA_CERT_PATH` | unset | optional TLS CA certificate path |
| `KAFKA_BROKER_URL` | `broker:29092` | Kafka bootstrap server |
| `INGESTION_KAFKA_RAW_TOPIC` | `transport-telemetry-raw` | accepted GPS topic |
| `INGESTION_KAFKA_DLQ_TOPIC` | `transport-telemetry-dlq` | rejected GPS topic |
| `INGESTION_KAFKA_TRIP_LIFECYCLE_TOPIC` | `trip.lifecycle` | trip lifecycle topic |
| `INGESTION_TRIP_CACHE_CONSUMER_GROUP` | `ingestion-trip-cache` | lifecycle consumer group |
| `INGESTION_REQUIRE_ACTIVE_TRIP` | `true` | reject GPS without active trip |
| `INGESTION_TRIP_CACHE_REBUILD_TIMEOUT_SECONDS` | `60.0` | startup cache rebuild window |
| `INGESTION_STARTUP_BUFFER_MAX_MESSAGES` | `1000` | GPS buffer during cache rebuild |
| `INGESTION_SERVICE_PORT` | `8001` | health/metrics port |

`INGESTION_` aliases are preferred in deployment, but legacy names such as
`MQTT_BROKER_HOST` and `KAFKA_BROKER_URL` are still accepted.

## Code Map

| File | Main methods/classes | What they do |
|------|----------------------|--------------|
| `app/main.py` | `main`, `handle_shutdown` | starts producer, trip cache consumer, MQTT subscriber, and health server; shuts them down cleanly |
| `app/config.py` | `IngestionSettings` | loads env config and defaults |
| `app/mqtt_subscriber.py` | `MQTTSubscriber.connect/start/stop` | manages MQTT connection and loop |
| `app/mqtt_subscriber.py` | `on_connect`, `on_disconnect`, `on_message` | subscribes to GPS/heartbeat topics and routes incoming messages |
| `app/mqtt_subscriber.py` | `_process_payload` | validates GPS, buffers during cache rebuild, enriches with tripId, publishes valid/DLQ |
| `app/mqtt_subscriber.py` | `_process_heartbeat` | validates heartbeat and records metrics only |
| `app/mqtt_subscriber.py` | `_enrich_location`, `_reject` | attaches active `tripId`; sends rejected payloads to DLQ |
| `app/validator.py` | `validate_gps_location_payload` | validates G1 MQTT GPS without `tripId` |
| `app/validator.py` | `validate_gps_payload` | validates enriched Kafka GPS with required `tripId` |
| `app/validator.py` | `validate_heartbeat_payload` | validates heartbeat device status |
| `app/validator.py` | `StatefulValidator.validate` | checks future/stale timestamps, duplicates, order, and event-time interval |
| `app/trip_lifecycle_cache.py` | `ActiveTripCache.apply_event/get_active_trip` | maintains busId -> active trip in memory |
| `app/trip_lifecycle_cache.py` | `TripLifecycleConsumer.start/stop` | consumes `trip.lifecycle` in a background thread |
| `app/producer.py` | `publish_valid` | publishes accepted GPS to `transport-telemetry-raw` keyed by `busId` |
| `app/producer.py` | `publish_to_dlq` | publishes rejected GPS to `transport-telemetry-dlq` with metadata |
| `app/metrics.py` | `MetricsCollector` methods | tracks received, accepted, rejected, heartbeat, broker, and trip-cache metrics |
| `app/health.py` | `create_app`, `start_health_server` | exposes `/health`, `/health/live`, `/health/ready`, and `/metrics` |

## Run

Local Python:

```bash
python -m pip install -r services/ingestion/requirements.txt
python -m services.ingestion.app.main
```

Docker Compose:

```bash
docker compose -f docker/docker-compose.yml up -d broker mqtt-broker ingestion-service
```

Useful host checks:

```bash
curl http://localhost:8001/health
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready
curl http://localhost:8001/metrics
```

## Tests

```bash
python -m pip install -r services/ingestion/requirements-dev.txt
python -m pytest services/ingestion/tests/unit -q
python -m pytest services/ingestion/tests/integration/test_smoke_pipeline.py -q
```

Smoke coverage proves:

- Kafka, Mosquitto, and ingestion containers start
- `TRIP_STARTED` is consumed into the active-trip cache
- valid MQTT GPS reaches `transport-telemetry-raw` with enriched `tripId`
- invalid MQTT GPS reaches `transport-telemetry-dlq`
- `/health/ready` works in the container stack

## Ownership Notes

- Fleet owns trip start/end and publishes `trip.lifecycle`.
- G1 owns GPS and heartbeat publishing.
- Ingestion owns validation, active-trip gating, raw Kafka publish, DLQ publish,
  health, and metrics.
- Stream processing owns downstream route enrichment, ETA, anomaly, and live map
  outputs.
