# OnTime G2 - Increment 1 Restructure Plan v2

> Date: 2026-05-01
> Status: Approved restructure after cross-group meeting and internal review
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

## 2. Canonical Service Port Registry

All services must use these ports. Any conflicting references in other documents (STRATEGY.md, PROJECT_PLAN.md) must be updated to match this table.

| Service | Port | Status |
|---------|------|--------|
| API Gateway | 8000 | Existing |
| Ingestion Service | 8001 | Existing |
| Route Service | 8002 | Existing (was 8004 in STRATEGY.md, now corrected to 8002) |
| Fleet Management Service | 8003 | Existing |
| ETA Service | 8005 | New |
| Anomaly Service | 8006 | New |

> **Action for Kusal:** Update `STRATEGY.md` Section 2.2 Service Catalog to replace port 8004 with 8002 for Route Service. Add ETA Service (8005) and Anomaly Service (8006).

## 3. Internal Service URL Convention

Every service that calls another service must use environment variables for URLs. These are set in `docker-compose.yml`:

```
ROUTE_SERVICE_URL=http://route-service:8002
FLEET_SERVICE_URL=http://fleet-management-service:8003
ETA_SERVICE_URL=http://eta-service:8005
ANOMALY_SERVICE_URL=http://anomaly-service:8006
```

No service should hardcode another service's host or port.

## 4. Health Endpoint Standard

All 7 G2 services must expose the same health contract. Ingestion already implements this pattern. All other services must follow it:

```
GET /health          → { status, service, timestamp, dependencies }
GET /health/live     → 200 if process is alive
GET /health/ready    → 200 if all dependencies are up
GET /metrics         → Prometheus text format
```

This is required for G4's Kubernetes deployment (liveness/readiness probes) and Prometheus monitoring.

## 5. Current Repository Baseline

| Area | Current State | Next Required Action |
|------|---------------|----------------------|
| API Gateway | `services/api-gateway/` has health, metrics, dependency checks | Expand into the G2 internal gateway behind Kong, with REST aggregation and WebSocket live feed |
| Ingestion Service | `services/ingestion/` receives MQTT, validates GPS, publishes Kafka raw/DLQ | Change stateful validation to use payload event time; add active-trip filtering via Kafka cache |
| Route Service | `services/route-service/` has route list, route detail GeoJSON, stops, route search, progress, admin KML CRUD | Migrate to route-owned schema; expose all passenger route/search APIs through G2 API Gateway |
| Fleet Management Service | `services/fleet-management-service/` has bus CRUD, route assignment, route validation through route-service | Add trip lifecycle/state ownership and active-trip lookup for ingestion/live pipeline |
| Stream Processing | `services/stream-processing/` is currently a README placeholder | Implement PyFlink job for cleaned telemetry, routeId enrichment, Redis live feed, InfluxDB writes |
| ETA Service | `services/eta-service/` is currently a README placeholder | Implement service with replaceable mathematical ETA model |
| Anomaly Service | `services/anomaly-service/` is currently a README placeholder | Implement service with replaceable rule-based anomaly model |
| Docker Compose | Kafka, MQTT, Postgres, Redis, InfluxDB, API Gateway, Route, Fleet, Ingestion exist | Add Flink, ETA service, anomaly service, service env vars, and health checks |

## 6. Updated Architecture Decisions

### 6.1 Kong and G2 API Gateway Boundary

G4 owns the external platform gateway. G4 has confirmed Kong supports WebSocket proxy, so both REST and WebSocket traffic flow through Kong:

```text
Passenger / Driver / Admin
        |
        v
G4 Kong Gateway
  - authentication
  - CORS
  - public routing
  - rate limiting/security policies
  - WebSocket proxy (confirmed supported)
        |
        v
G2 API Gateway
  - single G2 access point
  - REST aggregation
  - WebSocket live feed (/v1/live)
  - calls internal G2 services via HTTP
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
- API Gateway calls Fleet Service via HTTP to start/end trips. API Gateway never writes directly to fleet_db.

### 6.2 Strict Microservice Ownership

Every service owns its data. No service should read or write another service's database directly.

| Service | Owns | Storage |
|---------|------|---------|
| Route Service | Routes, stops, route geometry, route search data | `route_db` schema inside shared Postgres (schema-level isolation) |
| Fleet Management Service | Buses, bus-route assignments, trips, active/inactive trip state | `fleet_db` (separate logical database) |
| Ingestion Service | No business database; validates and forwards telemetry | Kafka topics and in-memory validation state |
| Stream Processing | Stream state, cleaned live position outputs, telemetry writes | Flink state, Redis, InfluxDB |
| ETA Service | ETA predictions, ETA model metadata | `eta_db` schema inside shared Postgres |
| Anomaly Service | Anomaly rules, alerts, anomaly state | `anomaly_db` schema inside shared Postgres |
| API Gateway | No business data ownership; aggregation and WebSocket only | Redis read/pub-sub and internal service calls |
| G4 Auth Service | Users, roles, credentials, auth sessions | G4-owned auth database |

> **Database separation approach (action for Chamodh and Kusal):** For Increment 1, use schema-level isolation inside the same Postgres container rather than separate Postgres instances. This means creating `route_db`, `eta_db`, and `anomaly_db` as separate schemas (or logical databases) in the Postgres init scripts. Fleet already uses `fleet_db` as a separate logical database. This keeps infrastructure simple while enforcing ownership boundaries. Migrate to fully separate instances in production if needed.

Required cleanup:

- Move Route Service away from shared/default `ontime_db` toward `route_db` schema.
- Keep Fleet in `fleet_db`.
- Stop using shared DB access from scripts for business data except service-owned seed tools.
- If a service needs another service's data, use HTTP API or Kafka events. Never cross-read databases.

### 6.3 Active-Trip Lookup Strategy (Decided: Kafka Cache)

When Ingestion needs to check whether a bus/trip is active, it must **not** make a synchronous HTTP call to Fleet Service on every GPS message. That would add latency to the hot path and create a hard dependency (if Fleet is down, ingestion stops).

Instead, the decided approach is:

1. Fleet Service publishes trip lifecycle events to a mandatory Kafka topic: `trip.lifecycle`
2. Ingestion Service consumes `trip.lifecycle` and maintains a local in-memory cache of active trips
3. On each GPS message, Ingestion checks its local cache to determine if the bus/trip is active
4. If the cache has no entry for the bus/trip, the GPS is rejected to DLQ with reason `INACTIVE_TRIP`

This aligns with the event-driven architecture philosophy and keeps the GPS hot path fast.

> **Action for Chamodh:** Fleet Service must publish to `trip.lifecycle` on every start-trip and end-trip event.
> **Action for Janidu:** Ingestion Service must consume `trip.lifecycle` and maintain the active-trip cache.

### 6.4 Mandatory Kafka Topics (Contract Freeze)

| Topic | Producer | Consumer(s) | Payload | Required |
|-------|----------|-------------|---------|----------|
| `transport-telemetry-raw` | Ingestion | Stream Processing (Flink) | GPSMessage JSON | Yes |
| `transport-telemetry-dlq` | Ingestion | Debug/monitoring | Raw payload + error | Yes |
| `transport-telemetry-cleaned` | Stream Processing | ETA Service, Anomaly Service | Enriched GPS + routeId | Yes |
| `trip.lifecycle` | Fleet Service | Ingestion, Stream Processing | Trip start/end events | **Yes (mandatory, not optional)** |
| `transport-anomaly-alerts` | Anomaly Service | API Gateway | Alert events | Yes |
| `fleet:live` | Stream Processing | API Gateway (Redis Pub/Sub) | Live position delta | Yes |
| `eta:live` | ETA Service | API Gateway (Redis Pub/Sub) | ETA update | Yes |

> `trip.lifecycle` was listed as "optional" in the previous version. It is now **mandatory** because both Ingestion and Stream Processing depend on it for active-trip filtering.

## 7. Target Increment 1 Runtime Flow

### 7.1 GPS and Live Map Flow (Bypass Path)

```text
G1 GPS Device or Simulator
  -> MQTT topic: transport/bus/{busId}/location
  -> Ingestion Service (validates, checks active-trip cache)
  -> Kafka: transport-telemetry-raw
  -> PyFlink Stream Processing
       - cleans, deduplicates, applies watermarks
       - enriches with routeId from Fleet trip cache
       - enriches with route progress from cached route geometry
  -> Redis keys (bus:{busId}:position) and Redis Pub/Sub (fleet:live)
  -> G2 API Gateway WebSocket: /v1/live
  -> Kong (WebSocket proxy)
  -> G3 mobile/web live map
```

This is the direct live-location path. It must be fast and must not wait for ETA/anomaly models.

### 7.2 ETA and Anomaly Side Flow

```text
PyFlink cleaned + enriched telemetry
  -> Kafka: transport-telemetry-cleaned (includes routeId, remaining distance)
  -> ETA Service heuristic model (consumes enriched stream)
  -> Redis Pub/Sub: eta:live
  -> G2 API Gateway REST/WebSocket

PyFlink cleaned telemetry
  -> Kafka: transport-telemetry-cleaned
  -> Anomaly Service L1 rules (uses cached route geometry for off-route checks)
  -> Kafka: transport-anomaly-alerts
  -> G2 API Gateway admin/alert APIs
```

ETA and anomaly are parallel enrichment paths. They do not block live bus position streaming. If ETA/anomaly services fail, the passenger live map still works.

### 7.3 routeId Enrichment (Decided: Flink enrichment)

The current `GPSMessage` schema has `busId` and `tripId` but no `routeId`. Rather than burdening G1 with data they don't own, Flink enriches GPS with `routeId`:

1. Flink consumes `trip.lifecycle` events and caches tripId-to-routeId mappings
2. When processing raw GPS, Flink looks up routeId from its trip cache
3. The enriched `transport-telemetry-cleaned` message includes routeId, remaining distance, and route progress

This means the WebSocket live feed can include routeId without changing the G1 payload contract.

When upgrading to real ML models in later increments, the ETA service can switch from receiving pre-computed distances to computing its own features from raw geometry. The Flink enrichment layer provides a clean extension point for this.

## 8. The WebSocket Bypass Path Explained

The live map needs one thing immediately: the latest trusted bus location. If every location update waits for ETA model inference or anomaly checks, the map becomes slow or fragile.

So Increment 1 uses a bypass path:

```text
Validated GPS -> Flink cleaning + enrichment -> Redis Pub/Sub -> API Gateway WebSocket
```

This bypass does not mean skipping validation. It means:

- GPS still passes schema validation, geo-bounds validation, active-trip validation, and stream cleaning.
- Cleaned and enriched location goes directly to WebSocket via Redis.
- ETA and anomaly services receive the same cleaned stream in parallel via Kafka.
- If ETA/anomaly services fail, passenger live map still works.
- If the live stream fails, ETA/anomaly should not hide that failure.

WebSocket message example (location):

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

ETA sent as separate event:

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

## 9. Ingestion Changes After G1 Meeting

### 9.1 Timestamp is Required — Missing Timestamp Goes to DLQ

The current `schemas/gps.py` has `timestamp` with a `default_factory` that fills server time when G1 omits it. This is incorrect for event-time processing and buffered replay.

**Decision:** `timestamp` is now a required field with no default. If G1 does not include `timestamp` in the payload, the message is rejected to DLQ with reason `MISSING_TIMESTAMP`.

This is a breaking change. Required coordination:

- **Kusal:** Update `schemas/gps.py` to remove the `default_factory`. Make timestamp required with no default.
- **Kusal:** Update `scripts/gps_simulator.py` to always include timestamp.
- **Janidu:** Ensure the validator catches missing timestamp and routes to DLQ.
- **Team lead:** Communicate to G1 that timestamp is mandatory in every GPS payload.

### 9.2 Buffered GPS Replay

G1 may buffer GPS while offline and flush after reconnecting. Stateful validation must not reject valid buffered data just because it arrives quickly.

Required changes:

- Validate rate and sequence using payload `timestamp`, not G2 receive time.
- Use an event-time threshold: `INGESTION_MIN_EVENT_INTERVAL_SECONDS=1.0`.
- Keep duplicate detection by bus, timestamp, lat, lon, and trip ID.
- Add future timestamp and old replay limits.

### 9.3 24-Hour Pulse vs Active GPS

G1 continuous device health is acceptable, but it must not be treated as passenger-facing GPS.

Rules:

- GPS location data should be accepted into live tracking only for active trips (checked via Kafka trip.lifecycle cache).
- Inactive bus GPS should be dropped or sent to DLQ with `INACTIVE_TRIP`.
- Device health should use a separate heartbeat topic: `transport/bus/{busId}/heartbeat`.

### 9.4 HiveMQ vs Mosquitto

No major logic change is needed if G1 moves from Mosquitto to HiveMQ. Changes are configuration-only:

```text
MQTT_BROKER_HOST=<hivemq-cloud-host>
MQTT_BROKER_PORT=8883
MQTT_USERNAME=<username>
MQTT_PASSWORD=<password>
MQTT_TLS_ENABLED=true
```

## 10. Increment 1 Service Scope

### 10.1 API Gateway (Port 8000)

Purpose:

- Single G2 entry point behind Kong.
- Aggregates Route, Fleet, ETA, and live stream data.
- Owns WebSocket connection handling.
- Does not own business databases.
- Calls Fleet Service via HTTP for trip start/end (never writes to fleet_db directly).

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
| POST | `/api/v1/driver/start-trip` | Driver starts active trip (Gateway -> Fleet HTTP) |
| POST | `/api/v1/driver/end-trip` | Driver stops active trip (Gateway -> Fleet HTTP) |
| POST | `/api/v1/driver/report-delay` | Driver reports delay |
| WS | `/v1/live` | Live bus positions and ETA deltas |

### 10.2 Route Service (Port 8002)

Purpose:

- Own route and stop data.
- Serve route geometry to API Gateway, Fleet validation, ETA, and anomaly checks.
- No direct bus ownership.

Required changes:

- Use route-owned database schema (`route_db`).
- Keep GeoJSON and stop APIs.
- Keep admin KML CRUD.
- Remove or deprecate route-owned `/api/v1/routes/{route_id}/buses` placeholder; bus data belongs to Fleet or API Gateway aggregation.

### 10.3 Fleet Management Service (Port 8003)

Purpose:

- Own buses, route assignment, and trip lifecycle.
- Know whether a bus/trip is active.
- Validate route IDs via Route Service API, not by reading route DB.
- Publish trip lifecycle events to Kafka `trip.lifecycle` topic (mandatory).

Required additions:

- `trips` table/model.
- Start trip endpoint (called by API Gateway via HTTP).
- End trip endpoint (called by API Gateway via HTTP).
- Active trip lookup endpoint for internal use:

```text
GET /internal/fleet/trips/active?busId=BUS-001&tripId=TRIP-001
```

- Kafka producer for `trip.lifecycle`:

```json
{
  "event": "TRIP_STARTED",
  "busId": "BUS-001",
  "tripId": "TRIP-001",
  "routeId": "202",
  "timestamp": "2026-05-01T10:00:00Z"
}
```

### 10.4 Ingestion Service (Port 8001)

Purpose:

- MQTT to Kafka bridge.
- Validate schema, geo bounds, event-time sequence, duplicates, and active trip.
- Publish valid data to raw telemetry topic.
- Send invalid data to DLQ with reason (including `MISSING_TIMESTAMP` and `INACTIVE_TRIP`).
- Consume `trip.lifecycle` topic to maintain active-trip cache.

### 10.5 Stream Processing Service (PyFlink)

Purpose:

- PyFlink job for event-time stream processing.
- Clean telemetry, apply watermarks, deduplicate.
- Enrich GPS with `routeId` and route progress by consuming `trip.lifecycle` and caching route geometry from Route Service at startup.
- Write live position state to Redis and publish via Redis Pub/Sub.
- Write historical telemetry to InfluxDB.
- Produce enriched events for ETA and anomaly services.

Required outputs:

| Output | Target | Purpose |
|--------|--------|---------|
| `fleet:live` | Redis Pub/Sub | Direct WebSocket bypass path |
| `bus:{busId}:position` | Redis key | Latest position snapshot |
| `gps_readings` | InfluxDB | Historical telemetry |
| `transport-telemetry-cleaned` | Kafka | ETA/anomaly input (enriched with routeId, remaining distance) |

### 10.6 ETA Service (Port 8005)

Purpose:

- Provide ETA outputs now using a replaceable mathematical model.
- Later replace only the model file with actual ML.
- Consumes `transport-telemetry-cleaned` which already contains routeId and remaining distance (enriched by Flink).

Increment 1 model:

```text
etaSeconds = remainingDistanceMeters / max(currentSpeedMetersPerSecond, minimumSpeed)
```

Required design:

- Put model logic behind an interface in `services/eta-service/app/models/eta_model.py`.
- API/service layer should not care whether ETA comes from heuristic or XGBoost later.
- Response must include `modelVersion: "heuristic-v1"`.
- ETA should support stop-level predictions for passenger stop view.

When upgrading to real ML models in Increment 2+, the ETA service can:
- Switch to computing its own features directly from route geometry (option a)
- Use a feature store populated by a separate feature engineering pipeline (option b)
- Continue consuming Flink-enriched streams with additional ML-specific features (option c)

The replaceable model interface ensures this switch requires changing only the model file, not the service layer.

### 10.7 Anomaly Service (Port 8006)

Purpose:

- Provide anomaly outputs now using deterministic rules.
- Later replace/extend the model file with statistical/ML detection.
- Caches route geometry from Route Service at startup for off-route deviation checks.

Increment 1 rules:

- Stationary bus during active trip.
- Off-route deviation (uses cached route geometry, Haversine distance from polyline).
- Unrealistic speed.
- Communication loss during active trip.
- GPS received for inactive trip.

Required design:

- Put detection logic behind an interface in `services/anomaly-service/app/models/anomaly_model.py`.
- Cache route geometry at startup via Route Service API and refresh periodically.
- Alert output topic: `transport-anomaly-alerts`.

## 11. Member-by-Member Ownership

### Updated Ownership Map

| Member | Primary Ownership | Secondary Responsibility |
|--------|-------------------|--------------------------|
| Janidu | Ingestion Service | G1 MQTT contract, event-time validation, active-trip GPS filtering via Kafka cache |
| Chamodh | Route Service, Fleet Management Service, **ETA Service (with Nidharshan)** | Strict DB ownership for route/fleet, trip lifecycle APIs, trip.lifecycle Kafka producer |
| Nidharshan | G2 API Gateway, **ETA Service (with Chamodh)** | Kong integration point, REST aggregation, WebSocket, ETA heuristic interface |
| Natasha | Stream Processing and Anomaly Service | PyFlink, Redis live feed, InfluxDB writes, routeId enrichment, L1 anomaly rule model |
| Kusal | Infrastructure, schemas, simulator, integration tests | Docker Compose, shared contracts, CI, E2E demo flow, demo script |

> **ETA Service collaboration:** Chamodh and Nidharshan will work together on the ETA Service. Chamodh handles the data/model layer (since he owns route geometry critical for distance calculations), and Nidharshan handles the service/API layer (since he owns the API Gateway that exposes ETA endpoints). This balances workload since Route Service is mostly complete.

If existing service README ownership sections conflict with this table, update the README files to match this plan.

## 12. Member Subphases (Expanded)

### 12.1 Janidu — Ingestion Service

**Phase J1 — Contract Alignment and Schema Update**

- Confirm G1 MQTT payload with required `timestamp`, `busId`, `tripId`, `lat`, `lon`, `speed`, `heading`.
- Work with Kusal to update `schemas/gps.py`: remove `default_factory` from timestamp, make it strictly required.
- Add heartbeat contract separately from GPS location (`transport/bus/{busId}/heartbeat`).
- Add HiveMQ env config (`MQTT_TLS_ENABLED`, `MQTT_USERNAME`, `MQTT_PASSWORD`) without breaking local Mosquitto.
- Add `MISSING_TIMESTAMP` as a new DLQ rejection reason.
- Update validator to reject payloads missing timestamp to DLQ.
- **Tests:** Validate that missing timestamp → DLQ, valid timestamp → accepted.

**Phase J2 — Event-Time Validation**

- Replace receive-time rate limiting with payload timestamp interval checks.
- Set `INGESTION_MIN_EVENT_INTERVAL_SECONDS=1.0` (event-time based).
- Add future skew check: reject if `event_timestamp > now + MAX_FUTURE_SKEW`.
- Add stale replay check: reject if `event_timestamp < now - MAX_STALE_AGE`.
- Implement per-bus state tracker keyed by `busId` storing last accepted event timestamp, lat/lon, and payload hash.
- Add duplicate detection: reject if same busId sends same timestamp + same coordinates.
- Add sequence check: reject if incoming event timestamp is older than last accepted for same busId.
- **Tests:** Buffered replay after reconnect (multiple messages same receive time, different event times → accepted). Rapid duplicate → rejected. Out-of-order timestamp → rejected. Independent state across two buses.

**Phase J3 — Active Trip Gate (Kafka Cache)**

- Add Kafka consumer for `trip.lifecycle` topic in a background thread.
- Maintain `dict[str, ActiveTripInfo]` keyed by busId with tripId, routeId, and start time.
- On `TRIP_STARTED` event: add/update cache entry.
- On `TRIP_ENDED` event: remove cache entry.
- On each GPS message: check cache. If busId not in cache or tripId doesn't match → reject to DLQ with `INACTIVE_TRIP`.
- Handle cache cold-start: on service startup, consume all available `trip.lifecycle` messages to rebuild state before accepting GPS.
- **Tests:** GPS for active trip → accepted. GPS for inactive trip → DLQ. GPS after trip end → DLQ. Cache rebuild on restart.

**Phase J4 — Hardening and Documentation**

- Update metrics with new rejection reasons: `MISSING_TIMESTAMP`, `INACTIVE_TRIP`, `RATE_LIMIT_EVENT_TIME`, `FUTURE_TIMESTAMP`, `STALE_REPLAY`.
- Ensure all health endpoints follow the standard (`/health`, `/health/live`, `/health/ready`, `/metrics`).
- Add integration tests with real MQTT and Kafka in Docker.
- Document G1 integration steps and payload contract in `services/ingestion/README.md`.
- Update root README startup instructions if changed.

---

### 12.2 Chamodh — Route Service, Fleet Service, and ETA Service (Data/Model Layer)

**Phase C1 — Database Ownership Migration**

- Create `route_db` schema/database in Postgres init scripts (`docker/init/`).
- Update Route Service `DATABASE_URL` in docker-compose to point to `route_db`.
- Verify all Route Service ORM models, seed scripts, and queries work against `route_db`.
- Confirm Fleet Service stays in `fleet_db` (already done).
- Ensure Fleet never reads Route DB directly; route validation stays through Route Service HTTP API.
- **Tests:** Route Service starts and serves data from `route_db`. Fleet validates routes via HTTP call to Route Service.

**Phase C2 — Route Service Completion**

- Finalize route list, route detail, stop list, route search, KML admin CRUD (mostly done).
- Keep route geometry stable for ETA/anomaly calculations.
- Deprecate route-service `/{route_id}/buses` placeholder or clearly route it through API Gateway/Fleet.
- Add route geometry export endpoint for Flink/Anomaly cache loading:
  ```
  GET /internal/routes/geometry → returns all route geometries for cache loading
  ```
- Ensure health endpoints follow standard (`/health`, `/health/live`, `/health/ready`, `/metrics`).
- **Tests:** All existing route tests pass against `route_db`. New geometry export endpoint returns valid data.

**Phase C3 — Fleet Trip Lifecycle**

- Add `trips` table with columns: id, bus_id, trip_id (string), route_id, status (ACTIVE/ENDED), started_at, ended_at.
- Add `POST /internal/fleet/trips/start` endpoint (called by API Gateway).
- Add `POST /internal/fleet/trips/end` endpoint (called by API Gateway).
- Add `GET /internal/fleet/trips/active?busId=...&tripId=...` endpoint.
- Add Kafka producer for `trip.lifecycle` topic. On start-trip: publish `TRIP_STARTED` with busId, tripId, routeId, timestamp. On end-trip: publish `TRIP_ENDED`.
- Validate that bus exists and route is valid before starting trip.
- Prevent starting a new trip if bus already has an active trip.
- Ensure health endpoints follow standard.
- **Tests:** Start trip → DB updated + Kafka event published. End trip → DB updated + Kafka event published. Double start → rejected. Active trip lookup returns correct data.

**Phase C4 — ETA Service Data/Model Layer (with Nidharshan)**

- Create ETA service directory structure: `services/eta-service/app/models/`, `services/eta-service/app/services/`.
- Implement `eta_model.py` with the heuristic interface:
  ```python
  class ETAModel:
      def predict(self, remaining_distance_m, current_speed_mps, ...) -> ETAPrediction
  ```
- Heuristic implementation: `eta_seconds = remaining_distance_m / max(current_speed_mps, MIN_SPEED)`.
- Return `model_version: "heuristic-v1"` and `confidence` score.
- Support stop-level predictions: given a list of remaining stops with distances, return ETA for each.
- **Tests:** Heuristic model returns correct ETA for known inputs. Zero speed uses minimum speed fallback. Stop-level predictions are ordered correctly.

**Phase C5 — Tests and Documentation**

- Add tests for trip lifecycle, active-trip lookup, and ETA model.
- Document service boundaries and database ownership in Fleet and Route READMEs.
- Document ETA model interface for future ML replacement.

---

### 12.3 Nidharshan — API Gateway and ETA Service (API Layer)

**Phase N1 — Gateway Restructuring**

- Convert API Gateway from single-file `main.py` into proper layered structure:
  ```
  services/api-gateway/
    app/
      __init__.py
      main.py
      routers/         (route_routes.py, fleet_routes.py, eta_routes.py, driver_routes.py, live.py)
      services/        (route_client.py, fleet_client.py, eta_client.py)
      models/          (response models)
  ```
- Add internal service HTTP clients using `httpx.AsyncClient` for Route, Fleet, ETA, and Anomaly services.
- Use environment variables for service URLs (see Section 3).
- Accept identity/role headers from Kong (e.g., `X-User-Id`, `X-User-Role`).
- Ensure health endpoints follow standard.
- **Tests:** Service client correctly forwards requests. Health endpoint returns dependency statuses.

**Phase N2 — Passenger and Driver REST APIs**

- Expose route endpoints by proxying to Route Service: `GET /api/v1/routes`, `GET /api/v1/routes/search`, `GET /api/v1/routes/{routeId}`, `GET /api/v1/routes/{routeId}/stops`.
- Expose fleet endpoints by proxying to Fleet Service: `GET /api/v1/fleet/buses`, `GET /api/v1/fleet/buses/route/{routeId}`.
- Expose ETA endpoints by proxying to ETA Service: `GET /api/v1/eta/routes/{routeId}`, `GET /api/v1/eta/buses/{busId}`.
- Add driver action endpoints that call Fleet Service via HTTP:
  - `POST /api/v1/driver/start-trip` → calls Fleet `POST /internal/fleet/trips/start`
  - `POST /api/v1/driver/end-trip` → calls Fleet `POST /internal/fleet/trips/end`
  - `POST /api/v1/driver/report-delay` → stores delay offset for ETA adjustment
- Keep internal service URLs hidden from user traffic.
- **Tests:** Each proxy endpoint returns correct data from downstream service. Driver endpoints correctly call Fleet.

**Phase N3 — WebSocket Live Feed**

- Implement `WS /v1/live` endpoint.
- On WebSocket connect: read latest fleet snapshot from Redis keys `bus:*:position` and send as initial state.
- Then subscribe to Redis Pub/Sub channels `fleet:live` and `eta:live` and stream deltas to connected clients.
- Support optional query params for route/bus filtering (e.g., `?routeId=202`).
- Handle connection lifecycle: clean up Redis subscriptions on disconnect.
- **Tests:** WebSocket connects and receives initial state. Redis Pub/Sub messages are forwarded to clients. Disconnect cleans up subscriptions.

**Phase N4 — ETA Service API Layer (with Chamodh)**

- Create ETA service FastAPI app: `services/eta-service/app/main.py`.
- Add Kafka consumer for `transport-telemetry-cleaned` in background thread.
- On each enriched GPS event: run Chamodh's `ETAModel.predict()` with remaining distance and speed from enriched stream.
- Write ETA predictions to Redis Pub/Sub `eta:live` for WebSocket.
- Expose REST API:
  - `GET /api/v1/eta/routes/{routeId}` → latest ETA for all active buses on route
  - `GET /api/v1/eta/buses/{busId}` → latest ETA for specific bus
- Add Dockerfile for ETA service.
- Ensure health endpoints follow standard.
- **Tests:** Kafka message triggers ETA prediction. REST endpoints return latest predictions. Model version is included in response.

---

### 12.4 Natasha — Stream Processing and Anomaly Service

**Phase T1 — PyFlink Job Skeleton**

- Add PyFlink job structure in `services/stream-processing/`.
- Set up PyFlink Docker images (JobManager + TaskManager) in docker-compose.
- Create Flink job that connects to Kafka and consumes `transport-telemetry-raw`.
- Apply event-time watermarks using payload timestamp.
- Verify Flink starts and consumes messages end-to-end.
- **Tests:** Flink job starts without errors. Messages from raw topic are consumed.

**Phase T2 — Clean, Enrich, and Publish Live Position**

- Deduplicate by bus/trip/timestamp within event-time windows.
- Apply simple sanity checks (speed bounds, coordinate bounds).
- Consume `trip.lifecycle` events and maintain tripId-to-routeId cache within Flink state.
- Cache route geometry from Route Service at startup (`GET /internal/routes/geometry`).
- Enrich each GPS message with: `routeId` (from trip cache), remaining distance to next stops (from cached geometry), route progress percentage.
- Write latest enriched position to Redis key `bus:{busId}:position`.
- Publish live delta to Redis Pub/Sub `fleet:live`.
- Write historical GPS to InfluxDB measurement `gps_readings`.
- **Tests:** Enriched messages contain routeId. Redis keys are updated. InfluxDB receives writes.

**Phase T3 — Cleaned Stream for ETA/Anomaly**

- Publish enriched telemetry to Kafka `transport-telemetry-cleaned`.
- Enriched message schema includes: all original GPS fields + routeId + remainingDistanceToNextStops + routeProgressPct.
- Ensure ETA and Anomaly services can consume this topic independently.
- **Tests:** Cleaned topic receives enriched messages. Schema matches expected fields.

**Phase T4 — Anomaly Service**

- Create anomaly service structure: `services/anomaly-service/app/`.
- Implement L1 rule model in `anomaly_model.py`:
  - Stationary bus: speed < 2 km/h for > 5 min during active trip.
  - Off-route deviation: Haversine distance > 50m from cached route polyline.
  - Unrealistic speed: speed > 120 km/h.
  - Communication loss: no telemetry > 3 min during active trip.
  - Inactive GPS: GPS received for inactive trip.
- Cache route geometry from Route Service at startup and refresh periodically.
- Consume `transport-telemetry-cleaned` from Kafka.
- Publish alerts to `transport-anomaly-alerts` Kafka topic.
- Add Dockerfile for anomaly service.
- Ensure health endpoints follow standard.
- **Tests:** Each rule triggers correctly. Alerts are published to correct topic. Model version `rules-v1` is included.

---

### 12.5 Kusal — Infrastructure, Schemas, Simulator, Integration

**Phase K1 — Docker Stack Expansion**

- Add PyFlink JobManager and TaskManager to docker-compose.
- Add ETA Service (port 8005) to docker-compose.
- Add Anomaly Service (port 8006) to docker-compose.
- Add all internal service URL environment variables (Section 3) to every service in docker-compose.
- Add `route_db`, `eta_db`, `anomaly_db` to Postgres init scripts.
- Add health checks for all new services.
- Keep local Mosquitto but allow HiveMQ config via environment.
- Verify `docker compose up` starts the complete stack with all services healthy.
- **Tests:** All services start. All health endpoints return 200. No crash loops.

**Phase K2 — Shared Schemas**

- Update `schemas/gps.py`: make `timestamp` required with no default (remove `default_factory`).
- Add `schemas/trip_lifecycle.py` with `TripLifecycleEvent` model (event type, busId, tripId, routeId, timestamp).
- Add `schemas/websocket_events.py` with `BusLocationUpdate` and `ETAUpdate` models if useful for type safety.
- Add `schemas/enriched_gps.py` with enriched GPS fields (routeId, remainingDistance, routeProgress).
- Version shared schemas carefully. Schema changes require PR review from all affected members.
- **Tests:** Schema validation works for all new models. Old invalid payloads are correctly rejected.

**Phase K3 — Simulator Enhancement**

- Update simulator to always include timestamp (required after schema change).
- Simulate active trip start/end by publishing to `trip.lifecycle` topic or calling Fleet API.
- Simulate GPS every 3 to 5 seconds during active trip.
- Simulate offline buffering and replay after reconnect: accumulate messages, then flush with original event timestamps.
- Simulate heartbeat separately from GPS on `transport/bus/{busId}/heartbeat`.
- Add configurable scenarios: normal trip, buffered replay, inactive bus, off-route deviation.
- **Tests:** Simulator produces valid payloads. Buffered replay messages have correct event timestamps.

**Phase K4 — Integration, Demo Tests, and Demo Script**

- End-to-end test: simulator → MQTT → ingestion → Kafka → Flink → Redis → WebSocket.
- Test inactive GPS rejection: send GPS for inactive bus → verify DLQ.
- Test ETA response: start trip → send GPS → verify ETA per stop is returned.
- Test route/fleet/gateway aggregation: verify API Gateway correctly proxies all endpoints.
- Add load test for expected bus count (50 buses, 3-5 second intervals).
- **Create `scripts/demo_flow.py`** — a single script that demonstrates the complete Increment 1 flow:
  1. Create a bus via Fleet Service
  2. Start a trip via API Gateway
  3. Send GPS via MQTT simulator
  4. Verify WebSocket receives bus position updates
  5. Verify ETA is returned for route stops
  6. End the trip via API Gateway
  7. Send more GPS → verify it is rejected (DLQ)
  8. Print pass/fail summary
- **Tests:** Demo script runs end-to-end without errors. All assertions pass.

## 13. Global Subphases

### Phase 0 — Contract Freeze

- Freeze MQTT payload contract (timestamp required, no default).
- Freeze Kafka topic names (including mandatory `trip.lifecycle`).
- Freeze API Gateway public endpoints.
- Freeze service database ownership.
- Freeze internal service URL convention.
- Freeze health endpoint standard.

### Phase 1 — Microservice Alignment

- Route DB and Fleet DB separated (schema-level isolation).
- No direct cross-service DB reads.
- Kong → G2 API Gateway → internal services boundary documented.
- Internal service URL environment variables configured.

### Phase 2 — Correct Ingestion

- Event-time validation implemented.
- Active-trip filtering implemented via Kafka cache.
- Missing timestamp → DLQ.
- HiveMQ/Mosquitto config supported.

### Phase 3 — Live Stream

- PyFlink consumes raw telemetry.
- Flink enriches GPS with routeId and remaining distance.
- Redis live state and Pub/Sub ready.
- API Gateway WebSocket streams real cleaned and enriched data.

### Phase 4 — Heuristic Intelligence

- ETA service returns stop-level mathematical ETA (Chamodh model + Nidharshan API).
- Anomaly service returns L1 rule alerts.
- Models are isolated in replaceable files.

### Phase 5 — Integration Hardening

- Docker Compose starts the full stack (all 7 services + infrastructure).
- All health endpoints pass the standard contract.
- End-to-end demo path works via `scripts/demo_flow.py`.
- Tests and docs updated.

## 14. Acceptance Criteria for Increment 1 v2

- Users enter through Kong and reach only G2 API Gateway for G2 APIs.
- API Gateway exposes route, stop, bus, live location, ETA, and driver trip APIs.
- Driver can start and end a trip (API Gateway → Fleet Service HTTP → fleet_db).
- Fleet Service publishes trip lifecycle events to mandatory `trip.lifecycle` Kafka topic.
- GPS is accepted only for active bus/trip combinations (checked via Kafka cache in Ingestion).
- GPS without timestamp is rejected to DLQ with `MISSING_TIMESTAMP`.
- Buffered GPS replay is validated using payload timestamp, not receive time.
- Live map receives bus location updates through WebSocket within 2 seconds after stream processing.
- PyFlink enriches GPS with routeId and remaining distance before publishing to cleaned topic.
- ETA per stop is available using `heuristic-v1` (Chamodh model, Nidharshan API).
- Anomaly service produces L1 rule alerts using `rules-v1` with cached route geometry.
- Redis stores latest live positions and publishes live deltas.
- InfluxDB stores historical GPS readings.
- All services expose `/health`, `/health/live`, `/health/ready`, `/metrics`.
- All services use internal URL environment variables, no hardcoded hosts.
- Docker Compose starts the full stack with all services healthy.
- `scripts/demo_flow.py` runs the complete demo path end-to-end.
- Real ML can replace heuristic files later without changing API Gateway or frontend contracts.

## 15. Immediate Backlog

1. Update `schemas/gps.py` so timestamp is required with no default (Kusal).
2. Update ingestion stateful validation to use event time (Janidu).
3. Add `trip.lifecycle` Kafka producer to Fleet Service (Chamodh).
4. Add active-trip Kafka cache to Ingestion Service (Janidu).
5. Add API Gateway routers/services/models structure (Nidharshan).
6. Add WebSocket `/v1/live` (Nidharshan).
7. Add PyFlink job and Docker services (Natasha + Kusal).
8. Add ETA Service skeleton with `eta_model.py` (Chamodh model + Nidharshan API).
9. Add Anomaly Service skeleton with `anomaly_model.py` (Natasha).
10. Update docker-compose: route_db, eta_db, anomaly_db, Flink, ETA, anomaly services, all env vars (Kusal).
11. Add route geometry export endpoint for cache loading (Chamodh).
12. Update service README ownership sections to match this plan (all members).
13. Create `scripts/demo_flow.py` end-to-end demo script (Kusal).
14. Add end-to-end integration test (Kusal).

## 16. Final Increment 1 Definition

Increment 1 is complete when the system can demonstrate:

```text
Driver starts trip (API Gateway → Fleet Service → fleet_db + trip.lifecycle Kafka)
  -> Ingestion receives trip.lifecycle, caches active trip
  -> GPS begins sending (simulator or G1)
  -> Ingestion validates event-time GPS + active-trip check
  -> Kafka receives valid telemetry (transport-telemetry-raw)
  -> PyFlink cleans, enriches with routeId + remaining distance
  -> Redis publishes live position (fleet:live)
  -> API Gateway WebSocket sends enriched bus movement to G3
  -> ETA Service returns stop-level heuristic ETA (heuristic-v1)
  -> Anomaly Service produces basic rule alerts (rules-v1)
  -> Driver ends trip (API Gateway → Fleet Service → fleet_db + trip.lifecycle Kafka)
  -> Later GPS is rejected from live tracking (INACTIVE_TRIP → DLQ)
  -> GPS without timestamp is rejected (MISSING_TIMESTAMP → DLQ)
```

The real ML models are not required in Increment 1. What is required is the correct service boundary, correct data flow, the replaceable model interface, and the full health/metrics standard across all services.
