# OnTime G2 - Increment 1 Restructure Plan v2

> Date: 2026-05-01
> Status: Proposed restructure after cross-group meeting
> Scope: Complete Increment 1 end-to-end using strict microservice architecture, with mathematical/heuristic models replacing real ML models until later increments.

## 1. Why This Plan Exists

The previous Increment 1 plan assumed a smaller scope: ingestion, route service, a basic live feed, and later ETA/anomaly work. After the latest meeting, the Increment 1 target is broader:

- Route Service, Fleet Management Service, and Ingestion Service are already started/completed in the repository.
- G4 will own Kong API Gateway, auth, CORS, and their own auth database/service.
- G2 must still keep its own API Gateway as the single G2 access point behind Kong.
- G1 sends GPS every 5 seconds, may buffer data offline, and may flush buffered data after reconnecting.
- G1 may send continuous heartbeat/pulse messages, but G2 should not treat out-of-service GPS as live bus movement.
- G3/passengers need live map, route search, destination search, bus search, bus stop search, and ETA per stop.
- Increment 1 should include all major G2 services and working data flow, but real ML models can be replaced by mathematical model interfaces for now.

This plan replaces the old Increment 1 execution plan without rewriting the whole project strategy.

## 2. Current Repository Baseline

The current repo already contains these working pieces:

| Area | Current State | Next Required Action |
|------|---------------|----------------------|
| API Gateway | `services/api-gateway/` has health, metrics, dependency checks | Expand into the G2 internal gateway behind Kong, with REST aggregation and WebSocket live feed |
| Ingestion Service | `services/ingestion/` receives MQTT, validates GPS, publishes Kafka raw/DLQ | Change stateful validation to use payload event time; add active-trip filtering |
| Route Service | `services/route-service/` has route list, route detail GeoJSON, stops, route search, progress, admin KML CRUD | Align database ownership to strict microservice rules and expose all passenger route/search APIs through G2 API Gateway |
| Fleet Management Service | `services/fleet-management-service/` has bus CRUD, route assignment, route validation through route-service | Add trip lifecycle/state ownership and active-trip lookup for ingestion/live pipeline |
| Stream Processing | `services/stream-processing/` is currently a README placeholder | Implement Flink job for cleaned telemetry, Redis live feed, InfluxDB writes, ETA/anomaly feature outputs |
| ETA Service | `services/eta-service/` is currently a README placeholder | Implement service with replaceable mathematical ETA model |
| Anomaly Service | `services/anomaly-service/` is currently a README placeholder | Implement service with replaceable rule-based anomaly model |
| Docker Compose | Kafka, MQTT, Postgres, Redis, InfluxDB, API Gateway, Route, Fleet, Ingestion exist | Add Flink, ETA service, anomaly service, service env vars, and health checks |

## 3. Updated Architecture Decisions

### 3.1 Kong and G2 API Gateway Boundary

G4 owns the external platform gateway:

```text
Passenger / Driver / Admin
        |
        v
G4 Kong Gateway
  - authentication
  - CORS
  - public routing
  - rate limiting/security policies
        |
        v
G2 API Gateway
  - single G2 access point
  - REST aggregation
  - WebSocket live feed
  - calls internal G2 services
        |
        v
Route / Fleet / ETA / Anomaly / Stream outputs
```

Rules:

- Users must not call Route, Fleet, ETA, Anomaly, or Ingestion services directly.
- Kong should route user traffic only to G2 API Gateway for G2-owned APIs.
- G4 Auth Service and auth database are outside G2. G2 should not build user authentication storage.
- G2 API Gateway should trust verified identity/role claims forwarded by Kong, then apply G2-level authorization decisions where needed.
- Internal service-to-service traffic should stay on Docker/Kubernetes internal networks.

### 3.2 Strict Microservice Ownership

Every service owns its data. No service should read or write another service's database directly.

| Service | Owns | Storage |
|---------|------|---------|
| Route Service | Routes, stops, route geometry, route search data | `route_db` or route-owned schema/database |
| Fleet Management Service | Buses, bus-route assignments, trips, active/inactive trip state | `fleet_db` |
| Ingestion Service | No business database; validates and forwards telemetry | Kafka topics and in-memory validation state |
| Stream Processing | Stream state, cleaned live position outputs, telemetry writes | Flink state, Redis, InfluxDB |
| ETA Service | ETA predictions, ETA model metadata, delay offsets if persisted here | `eta_db` or service-owned store |
| Anomaly Service | Anomaly rules, alerts, anomaly state | `anomaly_db` or service-owned store |
| API Gateway | No business data ownership; aggregation and WebSocket only | Redis read/pub-sub and internal service calls |
| G4 Auth Service | Users, roles, credentials, auth sessions | G4-owned auth database |

Required cleanup:

- Move Route Service away from shared/default `ontime_db` toward `route_db` or an explicitly route-owned schema.
- Keep Fleet in `fleet_db`.
- Stop using shared DB access from scripts for business data except service-owned seed tools.
- If a service needs another service's data, use HTTP API or Kafka events.

## 4. Target Increment 1 Runtime Flow

### 4.1 GPS and Live Map Flow

```text
G1 GPS Device or Simulator
  -> MQTT topic: transport/bus/{busId}/location
  -> Ingestion Service
  -> Kafka: transport-telemetry-raw
  -> Flink Stream Processing
  -> Redis keys and Redis Pub/Sub channel: fleet:live
  -> G2 API Gateway WebSocket: /v1/live
  -> Kong
  -> G3 mobile/web live map
```

This is the direct live-location path. It must be fast and must not wait for ETA/anomaly models.

### 4.2 ETA and Anomaly Side Flow

```text
Flink cleaned telemetry
  -> Kafka: transport-telemetry-cleaned
  -> ETA Service heuristic model
  -> Kafka or Redis: eta:live / eta.predictions
  -> G2 API Gateway REST/WebSocket

Flink cleaned telemetry
  -> Kafka: transport-telemetry-cleaned
  -> Anomaly Service L1 rules
  -> Kafka: transport-anomaly-alerts
  -> G2 API Gateway admin/alert APIs
```

ETA and anomaly are parallel enrichment paths. They should not block live bus position streaming.

## 5. The WebSocket Bypass Path Explained

The live map needs one thing immediately: the latest trusted bus location. If every location update waits for ETA model inference or anomaly checks, the map becomes slow or fragile.

So Increment 1 must use a bypass path:

```text
Validated GPS -> Flink cleaning -> Redis Pub/Sub -> API Gateway WebSocket
```

This bypass does not mean skipping validation. It means:

- GPS still passes schema validation, geo-bounds validation, active-trip validation, and stream cleaning.
- Cleaned location goes directly to WebSocket.
- ETA and anomaly services receive the same cleaned stream in parallel.
- If ETA/anomaly services fail, passenger live map still works.
- If the live stream fails, ETA/anomaly should not hide that failure.

WebSocket message example:

```json
{
  "type": "bus.location.updated",
  "busId": "BUS-001",
  "tripId": "TRIP-001",
  "routeId": "202",
  "lat": 6.9271,
  "lon": 79.8612,
  "speed": 38.5,
  "heading": 92,
  "timestamp": "2026-05-01T10:15:30Z"
}
```

ETA can be sent as a separate event:

```json
{
  "type": "eta.updated",
  "busId": "BUS-001",
  "routeId": "202",
  "stopEtas": [
    {"stopId": 10, "etaSeconds": 180, "confidence": 0.65}
  ],
  "modelVersion": "heuristic-v1"
}
```

## 6. Ingestion Changes After G1 Meeting

### 6.1 Buffered GPS Replay

G1 may buffer GPS while offline and flush after reconnecting. Current stateful validation must not reject valid buffered data just because it arrives quickly.

Required changes:

- Validate rate and sequence using payload `timestamp`, not G2 receive time.
- Make `timestamp` required in `schemas/gps.py`; do not default missing timestamps to server time.
- Use an event-time threshold, for example `INGESTION_MIN_EVENT_INTERVAL_SECONDS=1.0`.
- Keep duplicate detection by bus, timestamp, lat, lon, and trip ID.
- Add future timestamp and old replay limits.

Validation rule example:

```text
If same bus/trip sends event timestamps 0.4 seconds apart:
  reject as RATE_LIMIT_EVENT_TIME

If same bus/trip sends event timestamps 5 seconds apart but both arrive in the same second after reconnect:
  accept
```

### 6.2 24-Hour Pulse vs Active GPS

G1 continuous device health is acceptable, but it must not be treated as passenger-facing GPS.

Rules:

- GPS location data should be accepted into live tracking only for active trips.
- Inactive bus GPS should be dropped or sent to DLQ with `INACTIVE_TRIP`.
- Device health should use a separate heartbeat topic:

```text
transport/bus/{busId}/heartbeat
```

Active trip gate:

```text
Driver taps Start Trip
  -> Kong authenticates
  -> G2 API Gateway calls Fleet Service
  -> Fleet Service marks trip ACTIVE
  -> Ingestion accepts GPS for busId + tripId

Driver taps End Trip
  -> Fleet Service marks trip ENDED
  -> Ingestion rejects/drops later GPS for that trip
```

Recommended Increment 1 implementation:

- Keep MQTT subscribed to the broad topic `transport/bus/+/location`.
- Filter inactive bus/trip messages inside ingestion or stream processing.
- Do not dynamically subscribe/unsubscribe per bus in Increment 1 unless the active-trip event flow is already stable.

Dynamic MQTT subscription is possible later, but active-trip filtering is safer for this increment.

### 6.3 HiveMQ vs Mosquitto

No major logic change is needed if G1 moves from Mosquitto to HiveMQ because both are MQTT brokers and the code uses `paho-mqtt`.

Changes may be needed only in configuration:

- Broker host
- Broker port
- Username/password
- TLS enablement
- Client ID
- QoS

For HiveMQ Cloud, expect:

```text
MQTT_BROKER_HOST=<hivemq-cloud-host>
MQTT_BROKER_PORT=8883
MQTT_USERNAME=<username>
MQTT_PASSWORD=<password>
MQTT_TLS_ENABLED=true
```

## 7. Increment 1 Service Scope

### 7.1 API Gateway

Purpose:

- Single G2 entry point behind Kong.
- Aggregates Route, Fleet, ETA, and live stream data.
- Owns WebSocket connection handling.
- Does not own business databases.

Public endpoints exposed through Kong:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/routes` | Passenger route list |
| GET | `/api/v1/routes/search` | Search routes by source/destination/nearby points |
| GET | `/api/v1/routes/{routeId}` | Route geometry and stops |
| GET | `/api/v1/routes/{routeId}/stops` | Stops for a route |
| GET | `/api/v1/fleet/buses` | Bus list, filtered by role if needed |
| GET | `/api/v1/fleet/buses/route/{routeId}` | Active/assigned buses by route |
| GET | `/api/v1/eta/routes/{routeId}` | ETA for all active buses/stops on route |
| GET | `/api/v1/eta/buses/{busId}` | ETA for a specific bus |
| POST | `/api/v1/driver/start-trip` | Driver starts active trip |
| POST | `/api/v1/driver/end-trip` | Driver stops active trip |
| POST | `/api/v1/driver/report-delay` | Driver reports delay |
| WS | `/v1/live` | Live bus positions and ETA deltas |

### 7.2 Route Service

Purpose:

- Own route and stop data.
- Serve route geometry to API Gateway, Fleet validation, ETA, and anomaly checks.
- No direct bus ownership.

Required changes:

- Use route-owned database/schema.
- Keep GeoJSON and stop APIs.
- Keep admin KML CRUD.
- Remove or deprecate route-owned `/api/v1/routes/{route_id}/buses` placeholder; bus data belongs to Fleet or API Gateway aggregation.

### 7.3 Fleet Management Service

Purpose:

- Own buses, route assignment, and trip lifecycle.
- Know whether a bus/trip is active.
- Validate route IDs via Route Service API, not by reading route DB.

Required additions:

- `trips` table/model.
- Start trip endpoint.
- End trip endpoint.
- Active trip lookup endpoint for ingestion/stream:

```text
GET /internal/fleet/trips/active?busId=BUS-001&tripId=TRIP-001
```

- Optional Kafka event:

```text
trip.lifecycle
```

### 7.4 Ingestion Service

Purpose:

- MQTT to Kafka bridge.
- Validate schema, geo bounds, event-time sequence, duplicates, and active trip.
- Publish valid data to raw telemetry topic.
- Send invalid data to DLQ with reason.

Required changes:

- Event-time validation.
- Timestamp required.
- Active-trip validation.
- HiveMQ-compatible configuration.
- Separate heartbeat handling.

### 7.5 Stream Processing Service

Purpose:

- Flink job for event-time stream processing.
- Clean telemetry.
- Apply watermarks.
- Write live position state to Redis.
- Publish WebSocket-ready location deltas to Redis Pub/Sub.
- Write historical telemetry to InfluxDB.
- Produce features/events for ETA and anomaly services.

Required outputs:

| Output | Target | Purpose |
|--------|--------|---------|
| `fleet:live` | Redis Pub/Sub | Direct WebSocket bypass path |
| `bus:{busId}:position` | Redis key | Latest position snapshot |
| `gps_readings` | InfluxDB | Historical telemetry |
| `transport-telemetry-cleaned` | Kafka | ETA/anomaly input |

### 7.6 ETA Service

Purpose:

- Provide ETA outputs now using a replaceable mathematical model.
- Later replace only the model file with actual ML.

Increment 1 model:

```text
etaSeconds = remainingDistanceMeters / max(currentSpeedMetersPerSecond, minimumSpeed)
```

Required design:

- Put model logic behind an interface, for example:

```text
services/eta-service/app/models/eta_model.py
```

- API/service layer should not care whether ETA comes from heuristic or XGBoost later.
- Response must include `modelVersion: "heuristic-v1"`.
- ETA should support stop-level predictions for passenger stop view.

### 7.7 Anomaly Service

Purpose:

- Provide anomaly outputs now using deterministic rules.
- Later replace/extend the model file with statistical/ML detection.

Increment 1 rules:

- Stationary bus during active trip.
- Off-route deviation.
- Unrealistic speed.
- Communication loss during active trip.
- GPS received for inactive trip.

Required design:

- Put detection logic behind an interface, for example:

```text
services/anomaly-service/app/models/anomaly_model.py
```

- Alert output:

```text
transport-anomaly-alerts
```

## 8. Member-by-Member Ownership

### Updated Ownership Map

| Member | Primary Ownership | Secondary Responsibility |
|--------|-------------------|--------------------------|
| Janidu | Ingestion Service | G1 MQTT contract, event-time validation, active-trip GPS filtering |
| Chamodh | Route Service and Fleet Management Service | Strict DB ownership for route/fleet, trip lifecycle APIs |
| Nidharshan | G2 API Gateway and ETA Service | Kong integration point, REST aggregation, WebSocket, ETA heuristic interface |
| Natasha | Stream Processing and Anomaly Service | Flink, Redis live feed, InfluxDB writes, L1 anomaly rule model |
| Kusal | Infrastructure, schemas, simulator, integration tests | Docker Compose, shared contracts, CI, E2E demo flow |

If existing service README ownership sections conflict with this table, update the README files to match this plan.

## 9. Member Subphases

### 9.1 Janidu - Ingestion Service

Phase J1 - Contract Alignment

- Confirm G1 MQTT payload with required `timestamp`, `busId`, `tripId`, `lat`, `lon`, `speed`, `heading`.
- Add heartbeat contract separately from GPS location.
- Add HiveMQ env config without breaking local Mosquitto.

Phase J2 - Event-Time Validation

- Make GPS timestamp required.
- Replace receive-time rate limiting with payload timestamp interval checks.
- Add future skew and stale replay checks.
- Add tests for buffered replay after reconnect.

Phase J3 - Active Trip Gate

- Call Fleet active-trip lookup or consume trip lifecycle cache.
- Reject/drop inactive GPS with clear reason.
- Ensure heartbeat can still be monitored separately.

Phase J4 - Hardening

- Update metrics with new rejection reasons.
- Add unit/integration tests.
- Document G1 integration steps.

### 9.2 Chamodh - Route and Fleet

Phase C1 - Database Ownership

- Move Route Service to route-owned DB/schema.
- Keep Fleet Service in `fleet_db`.
- Ensure Fleet never reads Route DB directly; route validation stays through Route Service API.

Phase C2 - Route Service Completion

- Finalize route list, route detail, stop list, route search, KML admin CRUD.
- Keep route geometry stable for ETA/anomaly calculations.
- Deprecate route-service bus placeholder or clearly route it through API Gateway/Fleet.

Phase C3 - Fleet Trip Lifecycle

- Add `trips` model/table.
- Add start-trip, end-trip, active-trip lookup.
- Emit or expose trip lifecycle state for ingestion and stream processing.

Phase C4 - Tests and Docs

- Add tests for trip lifecycle.
- Add tests for active-trip lookup.
- Document service boundaries and database ownership.

### 9.3 Nidharshan - API Gateway and ETA

Phase N1 - Gateway Structure

- Convert API Gateway from single-file skeleton into `routers/`, `services/`, `models/` layout.
- Add internal service clients for Route, Fleet, ETA, and Anomaly.
- Accept identity/role headers from Kong.

Phase N2 - Passenger and Driver REST APIs

- Expose route, stop, bus, fleet, and ETA APIs through G2 API Gateway.
- Add driver start-trip/end-trip/report-delay endpoints that call Fleet/ETA as needed.
- Keep internal services hidden from user traffic.

Phase N3 - WebSocket Live Feed

- Implement `/v1/live`.
- On connect, send latest Redis fleet snapshot.
- Then stream Redis Pub/Sub deltas from `fleet:live` and `eta:live`.
- Support route/bus filters from query params if needed.

Phase N4 - ETA Service

- Implement ETA service with replaceable `eta_model.py`.
- Use heuristic ETA in Increment 1.
- Return model version, confidence, and stop-level ETA.

### 9.4 Natasha - Stream Processing and Anomaly

Phase T1 - Flink Job Skeleton

- Add Flink job structure in `services/stream-processing/`.
- Consume `transport-telemetry-raw`.
- Use event-time watermarks from payload timestamp.

Phase T2 - Clean and Publish Live Position

- Deduplicate by bus/trip/timestamp.
- Apply simple sanity checks.
- Write latest position to Redis.
- Publish live delta to `fleet:live`.
- Write historical GPS to InfluxDB.

Phase T3 - ETA/Anomaly Feature Stream

- Publish cleaned telemetry to `transport-telemetry-cleaned`.
- Add route context from Route Service/cache.
- Add active trip context from Fleet/cache.

Phase T4 - Anomaly Service

- Implement L1 rule model in `anomaly_model.py`.
- Detect stationary, off-route, unrealistic speed, communication loss, inactive GPS.
- Publish alerts to `transport-anomaly-alerts`.

### 9.5 Kusal - Infrastructure, Schemas, Simulator, Integration

Phase K1 - Docker Stack

- Add Flink JobManager/TaskManager.
- Add ETA Service and Anomaly Service.
- Add all service health checks and env vars.
- Keep local Mosquitto but allow HiveMQ config.

Phase K2 - Shared Schemas

- Update `GPSMessage` timestamp behavior.
- Add trip lifecycle schema if needed.
- Add live WebSocket event schemas if useful.
- Version shared schemas carefully.

Phase K3 - Simulator

- Simulate active trip start/end.
- Simulate GPS every 3 to 5 seconds.
- Simulate offline buffering and replay after reconnect.
- Simulate heartbeat separately from GPS.

Phase K4 - Integration and Demo Tests

- End-to-end test: simulator -> MQTT -> ingestion -> Kafka -> Flink -> Redis -> WebSocket.
- Test inactive GPS rejection.
- Test ETA response for route stops.
- Test route/fleet/gateway aggregation.
- Add load test for expected bus count.

## 10. Global Subphases

### Phase 0 - Contract Freeze

- Freeze MQTT payload contract.
- Freeze Kafka topic names.
- Freeze API Gateway public endpoints.
- Freeze service database ownership.

### Phase 1 - Microservice Alignment

- Route DB and Fleet DB separated.
- No direct cross-service DB reads.
- Kong -> G2 API Gateway -> internal services boundary documented.

### Phase 2 - Correct Ingestion

- Event-time validation implemented.
- Active-trip filtering implemented.
- HiveMQ/Mosquitto config supported.

### Phase 3 - Live Stream

- Flink consumes raw telemetry.
- Redis live state and Pub/Sub ready.
- API Gateway WebSocket streams real cleaned data.

### Phase 4 - Heuristic Intelligence

- ETA service returns stop-level mathematical ETA.
- Anomaly service returns L1 rule alerts.
- Models are isolated in replaceable files.

### Phase 5 - Integration Hardening

- Docker Compose starts the full stack.
- All health endpoints pass.
- End-to-end demo path works.
- Tests and docs updated.

## 11. Acceptance Criteria for Increment 1 v2

- Users enter through Kong and reach only G2 API Gateway for G2 APIs.
- API Gateway exposes route, stop, bus, live location, ETA, and driver trip APIs.
- Driver can start and end a trip.
- GPS is accepted only for active bus/trip combinations.
- Buffered GPS replay is validated using payload timestamp, not receive time.
- Live map receives bus location updates through WebSocket within 2 seconds after stream processing.
- ETA per stop is available using `heuristic-v1`.
- Anomaly service produces L1 rule alerts using `rules-v1`.
- Flink is part of the Increment 1 pipeline.
- Redis stores latest live positions and publishes live deltas.
- InfluxDB stores historical GPS readings.
- All services have health endpoints, Docker wiring, and tests.
- Real ML can replace heuristic files later without changing API Gateway or frontend contracts.

## 12. Immediate Backlog

1. Update `schemas/gps.py` so timestamp is required and timezone-aware.
2. Update ingestion stateful validation to use event time.
3. Add active trip API in Fleet Service.
4. Add API Gateway routers/services/models structure.
5. Add WebSocket `/v1/live`.
6. Add Flink job and Docker services.
7. Add ETA Service skeleton with `eta_model.py`.
8. Add Anomaly Service skeleton with `anomaly_model.py`.
9. Update docker compose for route DB, ETA DB, anomaly DB, Flink, ETA, and anomaly services.
10. Update service README ownership sections to match this plan.
11. Add end-to-end integration test.

## 13. Final Increment 1 Definition

Increment 1 is complete when the system can demonstrate:

```text
Driver starts trip
  -> GPS begins sending
  -> Ingestion validates event-time GPS
  -> Kafka receives valid telemetry
  -> Flink cleans stream
  -> Redis publishes live position
  -> API Gateway WebSocket sends bus movement to G3
  -> ETA Service returns stop-level heuristic ETA
  -> Anomaly Service produces basic rule alerts
  -> Driver ends trip
  -> Later GPS is rejected from live tracking
```

The real ML models are not required in Increment 1. What is required is the correct service boundary, correct data flow, and replaceable model interface.
