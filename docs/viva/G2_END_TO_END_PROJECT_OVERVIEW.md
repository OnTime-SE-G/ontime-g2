# OnTime G2 End-to-End Project Overview

This document explains the whole G2 system in simple viva-friendly language.
It is based on the current `main` branch, the project planning documents, and
the open anomaly CR2 branch (`feat/anomaly-cr2`).

## 1. Short Explanation

OnTime is a real-time public transport platform. Group 2 owns the backend data
and intelligence layer. Our work starts when GPS data comes from a bus device
or simulator, validates and processes that data, enriches it with route and
trip context, pushes live bus locations to the frontend, calculates ETA, detects
anomalies, and supports crowd occupancy prediction.

The easiest way to explain G2 is:

```text
Bus GPS or simulator
  -> MQTT
  -> Ingestion Service
  -> Kafka raw topic
  -> Flink Stream Processing
  -> Redis live bus updates + Kafka cleaned stream + InfluxDB history
  -> WebSocket live feed, ETA Service, Anomaly Service
  -> G3 passenger/driver/admin UIs through G4 Kong
```

G2 is not mainly a CRUD system. It is an event-driven telemetry and analytics
pipeline.

## 2. Group Boundary

| Group | Responsibility | Interface with G2 |
|---|---|---|
| G1 | Bus hardware, GPS device, heartbeat messages | Publishes MQTT GPS and heartbeat topics |
| G2 | Data services, stream processing, ETA, anomaly, crowd intelligence | This repository |
| G3 | Passenger, driver, admin frontend | Calls REST/WebSocket through G4/Kong |
| G4 | Kong, auth, deployment, Kubernetes, monitoring | Deploys G2 images and exposes selected routes |

Important viva point: G3 should not directly call Kafka, Redis, PostgreSQL, or
internal services. Public traffic goes through G4 Kong and then to G2 API
Gateway or WebSocket Service.

## 3. Main Services

| Service | Port | Main job |
|---|---:|---|
| API Gateway | 8000 | REST facade for G3. Proxies route, stop, bus, trip, driver, admin, auth/user requests. |
| Ingestion Service | 8001 | MQTT to Kafka bridge. Validates GPS and heartbeat messages. Sends invalid data to DLQ. |
| Route Service | 8002 | Owns route, stop, KML import, geometry, route search, and internal route geometry APIs. |
| Fleet Management Service | 8003 | Owns buses, drivers, schedules, planned trips, trip state, and trip lifecycle events. |
| WebSocket Service | 8004 | Subscribes to Redis channels and pushes live updates to frontend clients. |
| ETA Service | 8005 | Predicts stop arrival times from ETA feature streams using XGBoost, SARIMA, then physics fallback. |
| Anomaly Service | 8006 | Detects operational anomalies from cleaned telemetry and DLQ events. |
| Crowd Sensing Service | 8007 | Accepts passenger crowd reports and predicts occupancy using ML plus live trust-weighted reports. |
| Stream Processing | Flink UI 8081 | PyFlink job that cleans, enriches, stores, and republishes telemetry. |

## 4. End-to-End Runtime Flow

### Step 1: Routes and fleet are prepared

Before buses move, the system needs route and fleet ground truth.

- Route Service imports KML files and stores route polylines and stops in
  PostgreSQL/PostGIS.
- Fleet Service stores buses, drivers, schedules, and planned trips.
- A bus is assigned to a route/trip before the driver starts it.

Simple viva explanation:

> Route Service knows where the road and bus stops are. Fleet Service knows
> which bus and driver are assigned to which trip.

### Step 2: Driver starts a trip

When a driver starts a planned trip:

```text
Driver/G3 UI
  -> G4 Kong
  -> G2 API Gateway
  -> Fleet Management Service
  -> fleet database updated
  -> Kafka topic: trip.lifecycle
```

Fleet publishes an event like:

```json
{
  "event": "TRIP_STARTED",
  "busId": "1",
  "tripId": "TRIP-001",
  "routeId": "202",
  "timestamp": "2026-05-02T10:00:00Z"
}
```

This event is important because downstream services use it to know that GPS for
this bus belongs to an active trip.

### Step 3: GPS enters through MQTT

The G1 bus device or our simulator publishes GPS to MQTT:

```text
transport/bus/{busId}/location
```

Example GPS payload:

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

The GPS payload should not come with `tripId` from G1. G1 only owns device data.
Trip context comes from Fleet.

### Step 4: Ingestion validates and publishes raw telemetry

Ingestion subscribes to MQTT, checks the message, and publishes to Kafka.

Current logic includes:

- JSON parsing.
- Pydantic schema validation.
- Timestamp validation.
- Heartbeat handling on a separate heartbeat topic.
- DLQ output for invalid messages.
- Support for a stateful active-trip mode and a CR1 stateless mode.

Main output topics:

| Topic | Meaning |
|---|---|
| `transport-telemetry-raw` | Accepted GPS data for stream processing |
| `transport-telemetry-dlq` | Rejected GPS or malformed data with error reason |

Simple viva explanation:

> Ingestion is the gate at the edge. It does not do heavy intelligence. It
> accepts structurally valid GPS and sends bad messages to a dead-letter topic.

### Step 5: Flink becomes the source of truth

Stream Processing is the main real-time processing engine. It consumes:

- `transport-telemetry-raw`
- `trip.lifecycle`

It then:

- applies event-time processing and deduplication,
- rejects impossible physics data such as out-of-bounds coordinates or
  unrealistic speed,
- enriches GPS with `tripId`, `routeId`, `tripStatus`, route progress, off-route
  distance, next stop, remaining distance, and stops ahead,
- writes latest position to Redis,
- publishes live position to Redis Pub/Sub,
- writes historical telemetry to InfluxDB,
- publishes cleaned/enriched events to Kafka for ETA and anomaly services.

Important CR1 idea:

> Classify, do not drop behavioral problems.

If the GPS is physically impossible, Flink can send it to `telemetry-invalid`.
If it is physically possible but suspicious, such as off-route movement, Flink
marks fields like `offRoute: true` and allows Anomaly Service to decide what
alert to raise.

Main outputs:

| Output | Consumer |
|---|---|
| Redis key `bus:{busId}:position` | API Gateway/WebSocket initial state |
| Redis channel `fleet:live` | WebSocket Service |
| Kafka `transport-telemetry-cleaned` | Anomaly Service, downstream analytics |
| Kafka `transport-eta-features` | ETA Service |
| Kafka `telemetry-invalid` | Observability/debugging |
| InfluxDB `gps_readings` | ML training and history |

### Step 6: WebSocket sends live updates

The WebSocket Service subscribes to Redis channels:

- `fleet:live`
- `eta:live`
- anomaly live channels depending on branch/config
- `crowd:live` in current config

Frontend clients connect to:

```text
WS /v1/live
WS /v1/live?routeId=202
WS /v1/live?busId=1
```

Simple viva explanation:

> Redis Pub/Sub is used for fast fan-out. WebSocket Service is only responsible
> for connected clients and broadcasting live JSON events.

### Step 7: ETA Service predicts arrival times

ETA Service consumes ETA-ready feature messages from:

```text
transport-eta-features
```

It expects fields such as:

- `tripId`
- `busId`
- `routeId`
- `nextStopId`
- `distanceToNextStop`
- `stopsAhead`
- `speed`
- `routeProgressPct`
- `timestamp`

ETA logic:

1. It keeps a per-trip speed smoothing window.
2. Old events are removed using a TTL so stale GPS does not ruin predictions.
3. It tries the model cascade:
   - XGBoost first,
   - SARIMA second,
   - deterministic physics fallback last.
4. It stores ETA snapshots in Redis.
5. It publishes live ETA events to `eta:live`.
6. It persists records into `eta_db` for history and analytics.

Simple viva explanation:

> ETA is a separate consumer. Live map does not wait for ETA. ETA reads the
> enriched stream and publishes its own live ETA updates.

### Step 8: Anomaly Service detects problems

Anomaly Service consumes:

- `transport-telemetry-cleaned`
- `transport-telemetry-dlq`

Current main behavior includes:

- `UNREALISTIC_SPEED`: speed above threshold.
- `OFF_ROUTE`: bus is too far from assigned route geometry.
- `PERSISTENT_OFF_ROUTE`: repeated off-route readings.
- `STATIONARY`: bus stopped for too long.
- `COMMUNICATION_LOSS`: bus stops sending telemetry.
- `TRIP_NOT_STARTED_DEVICE_ACTIVE`: repeated inactive-trip DLQ events.
- `ERRATIC_DRIVING`: Isolation Forest on a sliding summary vector.

The Isolation Forest does not directly read raw GPS points. The service first
builds features such as:

- max acceleration,
- min acceleration,
- speed variance,
- heading variance,
- average speed,
- sample count.

Then the model classifies whether the behavior is normal or anomalous.

Open CR2 branch (`feat/anomaly-cr2`) adds:

- DBSCAN-based spatial clustering for better stationary detection.
- `numpy` dependency for clustering.
- audience-targeted Redis channels:
  - `anomaly:passenger`
  - `anomaly:driver`
  - `anomaly:admin`

Simple viva explanation:

> Anomaly Service is the safety and operations brain. It watches the cleaned
> stream and raises alerts without blocking the live map.

### Step 9: Crowd Sensing predicts occupancy

Crowd Sensing is a newer service. It receives passenger crowd reports through:

```text
POST /api/v1/crowd/report
```

High-level flow:

```text
Passenger report
  -> Crowd Sensing API
  -> Kafka topic crowd-reports
  -> Crowd Report Consumer
  -> trust engine
  -> PostgreSQL crowd_sensing_db
```

Prediction flow:

```text
GET /api/v1/crowd/predict
  -> validate route and stop
  -> historical ML prediction from MLflow if available
  -> fetch live reports from last 20 minutes
  -> trust-weighted blending
  -> return occupancy label and confidence
```

The hybrid predictor uses:

- historical XGBoost/MLflow prediction,
- recent live passenger reports,
- passenger trust scores,
- confidence based on report count and average trust.

Simple viva explanation:

> Crowd Sensing combines AI history with live human feedback. It does not trust
> every passenger equally; it weights reports by passenger reputation.

## 5. Service-by-Service Logic

### API Gateway

Purpose:

- Single G2 REST facade behind G4 Kong.
- Proxies route and fleet APIs.
- Provides public route, stop, bus, driver, admin, trip, auth, and user-facing
  routes.
- Uses Redis for live bus snapshots where needed.

Main design idea:

> API Gateway should not own business data. It coordinates calls to private
> services.

### Route Service

Purpose:

- Own route and stop data.
- Import KML routes.
- Store geometry in PostgreSQL/PostGIS.
- Serve public route/stop APIs through the API Gateway.
- Serve internal route geometry to Flink and Anomaly Service.

Main logic:

- Parse KML.
- Extract route LineString coordinates.
- Extract stop Point placemarks.
- Store/reuse stops.
- Link stops to routes in order.
- Provide route search, progress, stops, and geometry APIs.

### Fleet Management Service

Purpose:

- Own buses, drivers, schedules, planned trips, trip assignment, and trip state.

Main logic:

- Create buses and drivers.
- Assign buses to routes after validating Route Service.
- Generate planned trips from schedules.
- Assign bus and driver to a planned trip.
- Start trip only when status and assignments are valid.
- End trip only when it is active or incident-reported.
- Publish `TRIP_STARTED`, `TRIP_ENDED`, and incident events to Kafka.

### Ingestion Service

Purpose:

- Bridge G1 MQTT messages into Kafka.

Main logic:

- Subscribe to GPS and heartbeat topics.
- Validate payloads.
- Publish valid raw GPS to Kafka.
- Publish invalid GPS to DLQ with typed reasons.
- Track metrics for received, accepted, rejected, broker state, and heartbeat.
- Expose `/health`, `/health/live`, `/health/ready`, `/metrics`.

### Stream Processing

Purpose:

- Real-time event processing using PyFlink.

Main logic:

- Consume raw GPS and trip lifecycle events.
- Apply watermarks and deduplication.
- Reject physically invalid telemetry.
- Maintain trip-route context.
- Fetch route geometry and stops.
- Compute route progress and stops ahead.
- Publish Redis live updates.
- Publish cleaned Kafka telemetry.
- Write history to InfluxDB.

### WebSocket Service

Purpose:

- Push live updates to frontend clients.

Main logic:

- Connect to Redis.
- Subscribe to live channels.
- Broadcast received JSON to connected WebSocket clients.
- Support filters like `routeId` and `busId`.
- Expose health, readiness, and metrics.

### ETA Service

Purpose:

- Predict estimated arrival time for upcoming stops.

Main logic:

- Consume ETA feature stream.
- Smooth speed by trip using a bounded deque.
- Ignore off-route events.
- Clean memory on trip end.
- Predict using model cascade:
  - XGBoost,
  - SARIMA,
  - physics.
- Publish to Redis `eta:live`.
- Store results in PostgreSQL.

### Anomaly Service

Purpose:

- Detect operational anomalies and alert operations/admin/driver/passenger
  channels.

Main logic:

- Consume cleaned telemetry.
- Consume DLQ events for inactive-trip alerts.
- Fetch route geometry for off-route checks.
- Use rules for speed, off-route, stationary, communication loss.
- Use Isolation Forest for behavioral anomalies.
- In CR2, use DBSCAN clustering for stationary detection and audience channels.
- Publish alerts to Kafka, Redis, and PostgreSQL.

### Crowd Sensing Service

Purpose:

- Predict crowd occupancy using live reports and historical ML.

Main logic:

- Accept crowd reports.
- Attach verified passenger ID from API Gateway header.
- Publish reports to Kafka.
- Consumer stores reports and updates passenger trust scores.
- Prediction endpoint validates route-stop relation.
- Prediction blends historical ML and live reports.

## 6. Main Data Contracts

### MQTT

| Topic | Purpose |
|---|---|
| `transport/bus/{busId}/location` | G1 live GPS |
| `transport/bus/{busId}/heartbeat` | Device health, not live movement |

### Kafka

| Topic | Producer | Consumer | Purpose |
|---|---|---|---|
| `trip.lifecycle` | Fleet | Ingestion, Flink, ETA cleanup | Trip start/end/incident state |
| `transport-telemetry-raw` | Ingestion | Flink | Accepted GPS |
| `transport-telemetry-dlq` | Ingestion | Anomaly/operators | Rejected GPS |
| `telemetry-invalid` | Flink | Operators | Physically invalid data |
| `transport-telemetry-cleaned` | Flink | Anomaly, analytics | Enriched GPS |
| `transport-eta-features` | Flink | ETA | ETA-specific feature stream |
| `transport-anomaly-alerts` | Anomaly | Admin/API/monitoring | Alert events |
| `crowd-reports` | Crowd API | Crowd consumer | Passenger crowd reports |

### Redis

| Redis item | Producer | Consumer | Purpose |
|---|---|---|---|
| `bus:{busId}:position` | Flink | API/WebSocket | Latest bus snapshot |
| `fleet:live` | Flink | WebSocket | Live bus movement |
| `eta:live` | ETA | WebSocket | Live ETA updates |
| `anomaly:live` or audience channels | Anomaly | WebSocket/admin clients | Live anomaly alerts |
| `eta:trip:{tripId}:snapshot` | ETA | ETA/API | Latest ETA snapshot |

## 7. Databases and Storage

| Storage | Used by | Purpose |
|---|---|---|
| PostgreSQL/PostGIS | Route | Routes, stops, geometry |
| PostgreSQL | Fleet | Buses, drivers, schedules, trips |
| PostgreSQL | ETA | ETA records and prediction history |
| PostgreSQL | Anomaly | Alert records |
| PostgreSQL | Crowd Sensing | Crowd reports and passenger trust |
| Redis | Stream/ETA/Anomaly/WebSocket | Live state and Pub/Sub |
| InfluxDB | Stream/ML | Historical telemetry for training |
| MLflow | ETA, Anomaly, Crowd | Model registry and artifact loading |

## 8. Docker and Deployment Picture

Local development uses:

```bash
docker compose -f docker/docker-compose.yml up -d --build
```

The compose stack contains infrastructure and services:

- PostgreSQL/PostGIS,
- Redis,
- InfluxDB,
- Kafka broker and topic init,
- Mosquitto MQTT,
- Flink JobManager and TaskManager,
- MLflow,
- all G2 services.

GitHub Actions builds and publishes Docker images to GHCR on `main`. Deployment
uses Kubernetes rollout commands when cluster credentials are available.

## 9. One-Minute Viva Script

Use this if they ask "Explain your project end to end":

> Our G2 project is the data and intelligence backend for OnTime. The bus device
> sends GPS through MQTT. Ingestion validates the message and publishes it to
> Kafka. Flink is our real-time source of truth. It reads raw GPS plus trip
> lifecycle events, removes impossible data, enriches each point with route,
> trip, progress, and stop-distance data, then writes live positions to Redis
> and cleaned telemetry back to Kafka. WebSocket Service reads Redis and pushes
> live updates to the frontend. ETA Service consumes ETA features and predicts
> arrival time using XGBoost, SARIMA, and physics fallback. Anomaly Service
> consumes cleaned telemetry and DLQ events to detect off-route, speed,
> stationary, communication-loss, and erratic-driving issues. Crowd Sensing
> collects passenger reports and combines them with ML plus trust scores to
> predict occupancy. We used microservices, event-driven architecture, shared
> schemas, Docker, CI, and tests to keep the system modular and verifiable.

## 10. What Is Already Strong in the Repo

- Service boundaries are clear.
- Kafka topics and Redis channels are documented.
- Most services use `config.py` and environment variables.
- CI exists per service.
- There are unit tests, integration tests, and a live pipeline E2E smoke test.
- The architecture evolved through CR1 and CR2 instead of random changes.

## 11. Honest Current Limitations

These are good to know in viva if asked about future work:

- Some docs are ahead of code or branch-dependent, especially anomaly CR2 and
  cleanup docs.
- `chore/docs-cleanup` is behind `main`, so it must be updated before merging.
- WebSocket/anomaly audience channels need final alignment after CR2.
- Some service structures still differ from the ideal standard.
- More load testing and production monitoring dashboards are future work.

