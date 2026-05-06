# SE Viva Prep - OnTime G2

This document is a simple speaking guide for explaining G2's work from a
Software Engineering point of view. It focuses on lifecycle, architecture,
design, implementation, testing, evolution, and project management.

## 1. One-Minute Project Summary

OnTime is a real-time public transport tracking system. G2 owns the data and
intelligence backend. Our work receives live GPS from G1, validates and
processes it, enriches it with trip and route context, stores live/historical
state, detects anomalies, and exposes useful APIs/live feeds to G3 through G4's
platform layer.

Simple flow:

```text
G1 GPS device
  -> MQTT broker
  -> G2 ingestion
  -> Kafka raw/DLQ topics
  -> Flink stream processing
  -> Redis live state + Kafka cleaned topic + InfluxDB history
  -> API Gateway / WebSocket / Anomaly / planned ETA
  -> G3 UI through G4 Kong
```

The important SE point: we did not build one big system blindly. We used
requirements, contracts, service boundaries, increments, tests, CI, PR reviews,
and documentation to control complexity.

## 2. Lifecycle Model We Followed

Our actual lifecycle is a hybrid:

```text
Plan-based upfront work
  + Agile incremental delivery
  + V-model style verification mapping
```

Why hybrid?

- Plan-based parts were needed because four groups must integrate. We needed
  early agreements for MQTT topics, Kafka topics, REST endpoints, service
  ownership, auth boundary, and deployment responsibilities.
- Agile parts were needed because the project changed as we learned. For
  example, ingestion changed from GPS carrying `tripId` to GPS having only
  `busId`, with G2 enriching `tripId` from Fleet's `trip.lifecycle`.
- V-model thinking was used to connect each requirement/design decision to a
  verification method. For example, ingestion schema decisions are checked by
  unit contract tests and smoke tests.

Our lifecycle in simple phases:

| Phase | What We Did | Evidence |
|---|---|---|
| Requirements | Identified group boundaries, GPS contract, live tracking, trip lifecycle, monitoring, auth/deployment needs | SRS/docs, README contracts |
| Architecture | Chose microservices, event-driven Kafka pipeline, MQTT ingestion, Flink processing, Redis live state, PostgreSQL/PostGIS, InfluxDB | root README architecture, service READMEs |
| Design | Defined service APIs, topics, schemas, env vars, health/metrics, data ownership | service READMEs, schemas, docs |
| Implementation | Built services incrementally through branches and PRs | Git history, PRs, commits |
| Verification | Unit tests, contract tests, integration smoke tests, CI checks | pytest suites, GitHub Actions |
| Integration | Cross-group contracts with G1/G3/G4, Docker Compose, live pipeline smoke | integration docs/tests |
| Evolution | Updated plans when constraints changed, e.g. active-trip gate, heartbeat, auth boundary, ETA plan | phase branches, review comments, docs |

## 3. How Architecture Works

### Main Architecture Style

We use a microservices and event-driven architecture.

```text
Microservices:
  API Gateway
  Route Service
  Fleet Management Service
  Ingestion Service
  Stream Processing
  WebSocket Service
  Anomaly Service
  Planned ETA Service
  Planned Auth wrapper boundary

Event backbone:
  MQTT for G1 device input
  Kafka for durable internal events
  Redis for live low-latency state
  InfluxDB for telemetry history
  PostgreSQL/PostGIS for route/fleet relational data
```

### What Each Major Component Does

| Component | Role |
|---|---|
| G1 device | Sends GPS and heartbeat to MQTT |
| MQTT broker | Device-to-backend input channel |
| Ingestion | Validates GPS, checks active trip, enriches with `tripId`, sends accepted GPS to Kafka, rejected GPS to DLQ |
| Fleet service | Owns buses, drivers, schedules, planned trips, and publishes `trip.lifecycle` events |
| Kafka | Durable event backbone for telemetry and lifecycle |
| Flink | Cleans and enriches GPS continuously, calculates route progress, writes live/history outputs |
| Redis | Stores latest live bus state and Pub/Sub messages for WebSocket |
| WebSocket service | Pushes live bus/ETA messages to G3 clients |
| Route service | Owns route, stop, and geometry data |
| Anomaly service | Rule-based detection from cleaned telemetry and DLQ |
| API Gateway | G2 facade for G3; calls private G2 services |
| G4 Kong/Auth | External routing, authentication, RBAC, TLS, deployment, monitoring |

### Why This Architecture

| Decision | Reason |
|---|---|
| Microservices | Different responsibilities and team ownership are separated |
| Kafka | Decouples ingestion, Flink, anomaly, ETA; supports replay and durability |
| MQTT | Suitable for IoT devices and unstable network connections |
| Flink | Designed for continuous stream cleaning, enrichment, and stateful event processing |
| Redis | Fast latest-state cache and Pub/Sub for live UI |
| InfluxDB | Efficient historical time-series telemetry storage |
| PostgreSQL/PostGIS | Strong relational and geospatial route data support |
| API Gateway | G3 has one G2 REST facade; internal services stay private |
| Kong/Auth in G4 | Security/platform concerns stay with platform group |

## 4. Requirements Engineering

We handled requirements at three levels.

### Functional Requirements

Examples:

- G1 GPS data must enter G2 reliably.
- Invalid GPS must not break the pipeline.
- GPS must only become live telemetry when a trip is active.
- Drivers can start/end trips.
- Fleet start/end events must affect ingestion and stream processing.
- Live bus data must be visible to UI through API/WebSocket.
- Anomaly alerts must be produced for abnormal situations.

### Non-Functional Requirements

Examples:

- Low latency for live position updates.
- Observability through `/health`, `/health/ready`, and `/metrics`.
- Maintainability through service boundaries.
- Deployment portability through Docker and Kubernetes-friendly env vars.
- Fault isolation through Kafka topics and DLQ.
- Security boundary through Kong/Keycloak.

### Interface Requirements

Examples:

- MQTT location topic: `transport/bus/{busId}/location`
- MQTT heartbeat topic: `transport/bus/{busId}/heartbeat`
- Kafka topics:
  - `trip.lifecycle`
  - `transport-telemetry-raw`
  - `transport-telemetry-dlq`
  - `transport-telemetry-cleaned`
  - `transport-anomaly-alerts`
- WebSocket:
  - `WS /v1/live`
- API:
  - `/api/v1/routes`
  - `/api/v1/driver/trips/{trip_id}/start`
  - `/api/v1/admin/fleet/*`

## 5. Design Process

Our design process was contract-first.

1. Identify service responsibility.
2. Decide who owns the data.
3. Define the interface: HTTP, MQTT, Kafka, Redis, or DB.
4. Write or update schemas/docs.
5. Implement locally.
6. Add focused tests.
7. Run full unit/integration verification.
8. Open PR and get review.
9. Update docs after decisions changed.

Example: active-trip design.

Problem:

```text
G1 device knows busId, but not tripId.
```

Design decision:

```text
Fleet publishes trip.lifecycle when driver starts/ends a trip.
Ingestion consumes trip.lifecycle and keeps busId -> active trip cache.
GPS without active trip goes to DLQ as INACTIVE_TRIP.
```

Why it is good:

- G1 device remains simple.
- Driver app is source of truth for active trip.
- Ingestion hot path is fast because it uses local cache, not REST call per GPS.
- Bad/inactive GPS is traceable through DLQ.

## 6. Implementation Practices

### Service Ownership

Each service is independently deployable and has its own responsibility.

Examples:

- Ingestion owns MQTT validation and raw/DLQ Kafka publish.
- Fleet owns trip lifecycle state.
- Route service owns route/stop data.
- Flink owns stream enrichment and live telemetry outputs.
- Anomaly owns alert rules.
- API Gateway owns REST aggregation.

### Branching And PRs

We used small phase branches and PRs.

Examples:

- `fix/ingestion-p1`, `fix/ingestion-p2`, `fix/ingestion-p5`
- Separate review branches for docs, websocket, anomaly, ETA plans, auth plans.

This helped us:

- isolate risk
- review each phase separately
- verify after each phase
- avoid mixing unrelated changes

### Configuration Management

Business/runtime tuning is handled through environment variables, not code edits.

Examples:

```text
MQTT_BROKER_HOST
KAFKA_BROKER_URL
INGESTION_MIN_EVENT_INTERVAL_SECONDS
INGESTION_MAX_FUTURE_SKEW_SECONDS
INGESTION_DUPLICATE_CACHE_SIZE
```

In production, G4 should manage these in Kubernetes ConfigMaps and Secrets.
G2 defines what the variable means; G4 sets the deployed value.

## 7. Verification And Validation

### Verification vs Validation

Verification:

```text
Did we build the system correctly?
```

Validation:

```text
Did we build the correct system for the user/project need?
```

Examples:

| Type | What We Checked |
|---|---|
| Unit tests | individual validators, clients, health, metrics, route/fleet logic |
| Contract tests | MQTT GPS has no `tripId`, heartbeat shape, docs contract |
| Integration tests | MQTT -> ingestion -> Kafka smoke |
| Live pipeline smoke | Fleet start trip -> MQTT GPS -> ingestion -> Flink -> Redis/WebSocket |
| CI | tests run automatically on PRs |
| Manual review | PR reviews catch architecture boundary violations |

### V-Model Mapping

| Left Side Design Artifact | Right Side Test/Check |
|---|---|
| SRS and user needs | acceptance criteria and demo |
| Architecture diagram | end-to-end smoke test |
| MQTT/Kafka contract | contract and integration tests |
| Service API design | unit/API tests |
| Schema design | Pydantic validation tests |
| Deployment design | Docker Compose, health checks, readiness probes |
| Monitoring design | `/metrics` endpoint checks |

### Why DLQ Is Important

DLQ means invalid data is not silently lost and does not crash the pipeline.

Example:

```text
Bad GPS or inactive-trip GPS
  -> transport-telemetry-dlq
  -> error_type and metadata preserved
  -> anomaly/debug/operations can inspect it
```

This is a reliability and observability design choice.

## 8. Testing Strategy

### Unit Testing

Used for deterministic logic:

- GPS schema validation
- timestamp validation
- duplicate detection
- active-trip cache
- fleet trip lifecycle
- route API logic
- anomaly rule model
- health and metrics output

### Integration Testing

Used when behavior crosses service boundaries:

- MQTT broker + ingestion + Kafka
- full live pipeline with Docker
- Fleet trip start -> `trip.lifecycle`
- ingestion active-trip cache
- raw Kafka output
- Flink cleaned output
- Redis snapshot
- WebSocket live path

### Why Not Only Manual Testing?

Manual testing proves a demo once. Automated tests protect the system from
regression when another member changes a branch. Since our system is distributed,
automated smoke tests are important.

## 9. Evolution And Change Handling

The project evolved several times, and we handled changes through docs, PRs, and
contract updates.

Important examples:

| Change | Reason | How We Handled It |
|---|---|---|
| GPS stopped carrying `tripId` | G1 device should be simple; trip is business state | ingestion enriches from `trip.lifecycle` |
| Added active-trip gating | avoid showing buses before driver starts trip | local cache from Kafka lifecycle |
| Added heartbeat | distinguish device health from live GPS | separate MQTT heartbeat topic, metrics only |
| Changed rate limiting to event-time | buffered GPS can arrive in bursts | validate by GPS timestamp, not receive time |
| Added DLQ anomaly idea | device on but trip not started should be visible | anomaly can consume DLQ `INACTIVE_TRIP` |
| Auth boundary clarified | G4 owns Keycloak/Kong | G2 stores only driver profile and `auth_user_id` |
| ETA plan changed | ETA should be trip-scoped, not bus-scoped | use `(tripId, stopId)` and Flink features |

This is a good SE story: we did not freeze a wrong design. We evolved it while
protecting contracts and tests.

## 10. Project Management

### Incremental Planning

We split work into increments:

- Increment 0: infrastructure, schemas, skeletons, base docs.
- Increment 1: GPS ingestion, live tracking, route/fleet services, Flink,
  WebSocket, anomaly basics.
- Later increments: ETA ML, deeper anomaly, scheduling, auth integration, more
  operational features.

### Agile Practices Used

- small branches
- PR reviews
- phase-by-phase delivery
- CI checks
- team ownership per service
- contract updates after review
- integration tests after risky changes

### Plan-Based Practices Used

- SRS and architecture docs
- service contract docs
- topic and endpoint naming
- group responsibility matrix
- risk register
- acceptance criteria

### Risk Management

| Risk | Mitigation |
|---|---|
| G1 hardware delay | G1 temp/simulator and MQTT contract tests |
| Contract mismatch between groups | explicit README/service contracts |
| Kafka topic missing in CI | `kafka-init` topic creation |
| Device sends GPS before trip starts | active-trip gate and DLQ |
| Stale retained MQTT GPS | GPS retained false, timestamp validation |
| Service failure hard to diagnose | health, readiness, metrics |
| UI needs auth before G4 ready | temporary Auth wrapper plan |
| No real ETA training data | physics model first, synthetic data for later ML only if clearly labelled |

## 11. Quality Attributes

| Quality Attribute | Design Support |
|---|---|
| Maintainability | service boundaries, README contracts, schemas |
| Scalability | Kafka decoupling, Flink stream processing, Redis live state |
| Reliability | DLQ, health checks, readiness, event replay |
| Observability | metrics, health endpoints, structured topic flow |
| Security | Kong/Keycloak boundary, private internal services |
| Testability | small services, unit tests, integration smoke tests |
| Evolvability | planned ETA/Auth contracts, feature increments |
| Performance | active-trip local cache, no REST call per GPS, Redis for live reads |

## 12. Key Design Defenses

### Why Microservices?

Because each subsystem has different responsibilities and different change
rates. Ingestion, fleet, route, stream processing, and anomaly detection can be
developed, tested, and deployed independently. It also matches team ownership.

### Why Kafka?

Kafka decouples services. Ingestion does not need to know who consumes GPS.
Flink, anomaly, ETA, and debugging tools can consume/replay events independently.
It is better than direct REST for high-frequency telemetry.

### Why MQTT Before Kafka?

MQTT is better for IoT devices. Kafka is better for backend durable streaming.
So ingestion bridges from device protocol to backend event protocol.

### Why Redis?

Kafka is durable, but not ideal for quick latest-state reads by UI. Redis gives
fast `bus:{busId}:position` lookup and Pub/Sub for live WebSocket updates.

### Why Flink?

Flink is designed for continuous stream processing: watermarks, event time,
state, deduplication, enrichment, and live feature generation.

### Why Not Put Everything In API Gateway?

API Gateway should aggregate and route. If it owns GPS processing, route
calculation, anomaly, and ETA, it becomes a monolith and a bottleneck.

### Why Active-Trip Gate?

A bus device may be on before the driver starts a trip. We should not show that
as live public service. Driver start trip is the business truth, so GPS is
accepted only when Fleet has an active trip.

### Why Heartbeat Separate From GPS?

GPS is movement data. Heartbeat is device health. If we mix them, a device status
packet might look like a location update. Separating them makes monitoring clean.

### Why Event-Time Validation?

Buffered GPS can arrive all at once after network recovery. Receive-time rate
limiting would reject valid buffered events. Event-time validation uses the
timestamp inside the GPS, so it is fairer and more correct.

### Why ETA Is Planned As `(tripId, stopId)`?

A bus can serve different routes on different trips. `busId` alone does not
identify the route context. `tripId` identifies the current journey, so ETA
should be trip-scoped.

## 13. Likely Cross Questions And Answers

### Q1: Is this pure Agile?

No. It is hybrid. We used plan-based upfront design for cross-group contracts
and architecture, then agile increments and PRs for implementation.

### Q2: Why not pure Waterfall?

Because requirements changed after integration discussions. For example,
`tripId` moved out of G1 GPS and into ingestion enrichment. A pure waterfall
approach would make that change painful.

### Q3: Where is V-model here?

We used V-model thinking by mapping each design artifact to verification:
schemas to schema tests, topic contracts to integration tests, architecture to
end-to-end smoke tests, deployment design to health/readiness checks.

### Q4: How do you know the architecture works?

We tested the flow from Fleet trip start to MQTT GPS to ingestion raw Kafka to
Flink cleaned telemetry to Redis/WebSocket in an end-to-end smoke test.

### Q5: Why should G4 not modify your Python code?

G2 owns business logic. G4 owns deployment, Kubernetes, Kong, secrets, probes,
and monitoring. They configure the container through env vars and ConfigMaps,
not by editing service logic.

### Q6: How do you handle invalid GPS?

Ingestion validates JSON, schema, timestamp, geography, active trip, duplicates,
and event-time rules. Rejected messages go to `transport-telemetry-dlq` with
error reason and metadata.

### Q7: What if device is on but driver has not started the trip?

Ingestion checks active-trip cache. If no active trip exists, GPS is rejected to
DLQ as `INACTIVE_TRIP`. Anomaly can turn repeated events into a
`TRIP_NOT_STARTED_DEVICE_ACTIVE` alert.

### Q8: What if driver starts trip but device is off?

Fleet publishes trip lifecycle, but no GPS arrives. Stream/anomaly can detect
communication loss when no telemetry is received for an active trip.

### Q9: Why not call Fleet REST API for every GPS to check trip?

That would add latency and create a dependency bottleneck on every GPS packet.
Instead, ingestion consumes `trip.lifecycle` once and maintains a local cache.

### Q10: Why not directly read another service database?

That breaks microservice boundaries. Services communicate through APIs/events.
Only the owning service should own and mutate its database model.

### Q11: Are you using AI/ML now?

Not for current anomaly. Current anomaly is rule-based. ETA ML is planned later.
We should not claim real ML without real data. First ETA should use a physics
model; later ML can use synthetic data carefully labelled until real data exists.

### Q12: How is security handled?

G4 owns Kong and Keycloak. Kong validates users and roles before forwarding to
G2. G2 internal services remain private. G2 only stores driver profile data, not
passwords.

### Q13: How does Prometheus get metrics?

Each service exposes `/metrics`. In Kubernetes, G4 uses internal service DNS and
ServiceMonitor/scrape config to scrape those endpoints. Metrics do not go
through the public API Gateway.

### Q14: What if Kafka topic does not exist?

In local/integration compose we use `kafka-init` to create deterministic topics.
In production, G4 should provision the topics before starting dependent services.

### Q15: What is your biggest technical risk?

Cross-group contract mismatch. We reduced it by documenting MQTT topics, Kafka
topics, API endpoints, schemas, deployment env vars, and ownership boundaries.

### Q16: What is your biggest remaining work?

ETA Service implementation, Auth integration with G4/Keycloak, alert read path
for admin UI, and hardening production deployment/monitoring with G4.

## 14. What To Emphasize To Sir

Say this clearly:

```text
Our focus was not only coding features. We followed SE practices:
requirements -> contracts -> architecture -> service design -> implementation
-> tests -> CI -> review -> documentation -> evolution.
```

Also say:

```text
We used plan-based design where coordination was needed, and agile increments
where learning and change were expected.
```

And:

```text
Each cross-group boundary is explicit: G1 uses MQTT, G3 uses REST/WebSocket,
G4 manages Kong/Auth/K8s/Prometheus, and G2 owns data processing services.
```

## 15. Quick Architecture Explanation To Memorize

```text
The device publishes GPS through MQTT. Ingestion validates it and only accepts
it if Fleet says the bus has an active trip. Valid GPS goes to Kafka raw topic,
invalid GPS goes to DLQ. Flink consumes raw GPS and trip lifecycle events,
enriches GPS with route context, writes latest state to Redis for live map,
writes history to InfluxDB, and publishes cleaned telemetry. WebSocket pushes
Redis live updates to G3. Anomaly consumes cleaned telemetry and DLQ to detect
issues. G4 wraps public access with Kong, auth, deployment, and monitoring.
```

## 16. Strong Closing Answer

If asked "What did you learn from the project?", answer:

```text
We learned that distributed systems are mostly about contracts and ownership.
The hard part was not only writing Python services. The hard part was deciding
who owns state, how data moves between groups, how to validate each boundary,
and how to keep the system testable and deployable as requirements changed.
```

