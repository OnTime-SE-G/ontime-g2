# OnTime G2 — Project Plan & Incremental Delivery Roadmap

> **Version:** 2.0  
> **Date:** April 2026  
> **Methodology:** Agile Scrum (2-week sprints)  
> **Status:** Planning

---

## 1. First Release Assumptions

Before reading the increments below, understand these ground rules for the **first release** (Increment 0 + 1):

| Assumption | Explanation |
|-----------|-------------|
| **Only Passenger & Driver roles** | No Scheduler UI or service. Scheduling and dispatch are done manually by operations staff outside the system. |
| **Buses run on a fixed timetable** | We assume a bus is available at its platform at the scheduled time. No bus–route conflict handling needed. |
| **Focus: after Driver taps "Start"** | The core system begins when a driver taps "Start Trip." Everything before that (scheduling, assignment) is manual. |
| **Bus state machine is the backbone** | Every feature depends on tracking bus state: `WAITING_AT_DEPOT → DEPARTED_ORIGIN → EN_ROUTE → ARRIVED_DESTINATION` with `INCIDENT_REPORTED` branching from `EN_ROUTE`. Admin resets `ARRIVED_DESTINATION → WAITING_AT_DEPOT`. |
| **No Flink in Increment 0** | Stream processing (Flink) is introduced in Increment 1. Increment 0 sets up infra only (Kafka, PostgreSQL, Redis). |
| **GPS Simulator replaces G1 hardware** | Until G1 delivers real GPS devices, we use a Python simulator that emits fake GPS data every 3–5 seconds to Kafka. |

---

## 2. Incremental Strategy Overview

The system is delivered in **modular increments**. Each increment produces a **fully working software version** that adds value without breaking existing functionality.

```
                    ┌──────────────────────┐
                    │   Increment 0        │  ◀── YOU ARE HERE
                    │   Foundation Infra    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Increment 1        │
                    │   GPS + Live Map     │
                    │   + Bus State Machine│
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                 │
    ┌─────────▼────────┐ ┌────▼──────────┐ ┌────▼──────────┐
    │  Increment 2     │ │ Increment 3   │ │ Increment 4   │
    │  ETA Engine      │ │ Trip Sched.   │ │ Anomaly &     │
    │                  │ │ & Dispatch    │ │ Incidents     │
    └─────────┬────────┘ └────┬──────────┘ └────┬──────────┘
              │                │                 │
              └────────────────┼─────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Increment 5+       │
                    │   Route Search,      │
                    │   Crowd Intelligence │
                    └──────────────────────┘
```

---

## 3. Increment Details

---

### Increment 0: Foundation Infrastructure (✅ COMPLETED)

**Goal:** Set up the base platform so all subsequent services can be built and deployed. Every team member should be able to `docker compose up` and have a working Dev environment. **Strictly bounded to infrastructure and empty API Skeletons (Zero business logic or HTTP stubs).**

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 1 (2 weeks) |
| **Deliverables** | Docker Compose stack, DB schemas, route seeding, GPS simulator, CI pipeline, FastAPI skeleton |

#### Acceptance Criteria

- [x] `docker compose up` brings up AutoMQ/Kafka + PostgreSQL + InfluxDB + Redis with zero errors
- [x] `python scripts/seed_routes.py` populates route + 20 stops in PostGIS
- [x] `python scripts/gps_simulator.py` publishes GPS messages to AutoMQ
- [x] `curl localhost:8000/health` returns 200 with dependency statuses
- [x] GitHub Actions runs lint + type check + tests on every push and passes

---

### Increment 1: GPS Pipeline & Live Tracking + Bus State Machine (🚀 ACTIVE)

**Goal:** Prove that data flows end-to-end from GPS to a live map using the *real* streaming architecture (AutoMQ → Flink → Redis → Gateway). We will enforce a strict 3-Layer pattern (`routers`, `services`, `models`). No mock HTTP endpoints are permitted; the pipeline must be fully native, relying exclusively on a mathematical heuristic "stub" isolated purely within the `models` layer.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 2–3 (4 weeks) |
| **Dependency** | Increment 0 infrastructure |
| **Services Built** | Ingestion Service, Stream Processing (basic Flink), API Gateway (enhanced) |

#### Scope of Development (Cross-Group Boundaries)

To ensure smooth integration, responsibilities for Increment 1 are strictly divided between the subsystem groups.

**What G2 (Data & Intelligence) Will Develop in Inc 1:**
- **Stream Processing (Flink):** Consuming from AutoMQ, cleaning the GPS data, applying spatial bounding boxes.
- **Ingestion Service:** Bridging the MQTT hardware signal to the AutoMQ `transport-telemetry-raw` topic.
- **Anomaly Detection (L1 Rule Engine):** Deterministic physics rules (e.g., stationary bus logic, off-route deviation).
- **ETA Data/Math Stub:** Implementing the core heuristic logic (`distance / speed`) that acts as the placeholder before the XGBoost ML model is introduced in Increment 2. *(No UI or Endpoints, strictly data layer).*

**What G3 & G4 Will Develop (Outside G2's Scope):**
- **Auth & Security Service (G4):** Keycloak integration, JWT validation.
- **CRUD & Route Services (G3/G4):** Basic REST operations for creating bus stops and fetching schedules.
- **Driver State Machine API (G3):** G3 will handle the business logic of transitioning trips to `EN_ROUTE` via the driver app. G2 simply consumes these state changes via Kafka.
- **Infrastructure Gateway (G4):** The external Kong API Gateway routing mobile requests.

#### 5-Member Task Distribution (G2 Only) — Service-Based Ownership

> **Philosophy:** Each member owns a **complete, deployable service** end-to-end (code, Dockerfile, tests, documentation). No shared "layers" — you own your service fully. Cross-service coordination happens through **shared schemas** and **defined communication contracts** documented below.

##### Service Ownership Map

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Increment 1 — Service Ownership                     │
│                                                                          │
│  Member 1                Member 2              Member 3                  │
│  ┌────────────────┐      ┌────────────────┐    ┌────────────────┐       │
│  │  API Gateway   │◀─────│  Stream        │◀───│  Ingestion     │       │
│  │  (FastAPI)     │ Redis│  Processing    │Kafka│  Service       │       │
│  │  Port 8000     │Pub/Sub│ (Flink)       │    │  Port 8001     │       │
│  └────────────────┘      └────────────────┘    └────────────────┘       │
│         ▲                        ▲                     ▲                 │
│         │                        │                     │                 │
│         │ DB/Redis        DB/InfluxDB              MQTT from G1         │
│         │                        │                                       │
│  Member 4                Member 5                                        │
│  ┌────────────────┐      ┌──────────────────────┐                       │
│  │  Route         │      │  Infrastructure      │                       │
│  │  Management    │      │  + GPS Simulator      │                       │
│  │  Port 8004     │      │  + Database Schemas   │                       │
│  └────────────────┘      └──────────────────────┘                       │
└──────────────────────────────────────────────────────────────────────────┘
```

| Member | Owns Service | Directory | Increment 1 Deliverables |
|--------|-------------|-----------|--------------------------|
| **Member 1** | **API Gateway** | `services/api-gateway/` | Engineer the strict 3-Layer backend (`routers/`, `services/`, `models/`). Implement the **Mathematical ETA Stub** (`distance / speed` heuristic) inside the `models/` layer. Build the WebSocket `/v1/live` endpoint that subscribes to **Redis Pub/Sub** for real-time fleet updates. Expose REST endpoints: `/api/v1/buses/live`, `/api/v1/driver/start-trip`, `/api/v1/driver/report-delay`, `/api/v1/trips/{id}/state`. Own the Dockerfile and service-level tests. |
| **Member 2** | **Stream Processing** | `services/stream-processing/` | Lead the **Apache Flink (PyFlink)** development. Write the stream processing job that: (1) consumes raw GPS from AutoMQ topic `transport-telemetry-raw`, (2) cleans and validates GPS data (bounding box, speed sanity, deduplication), (3) applies **L1 Rule Engine** anomaly checks (stationary bus, off-route deviation, comms loss), (4) publishes cleaned positions to **Redis Pub/Sub** for the API Gateway to consume, and (5) writes time-series data to **InfluxDB**. Own the Flink job configuration, Dockerfile, and job-level tests. |
| **Member 3** | **Ingestion Service** | `services/ingestion/` | Develop the MQTT-to-Kafka bridge service. Subscribe to G1's MQTT topic `transport/bus/{busId}/location`, validate incoming GPS payloads against the shared `GPSMessage` Pydantic schema, and produce valid messages to AutoMQ topic `transport-telemetry-raw`. Route invalid/malformed messages to `transport-telemetry-dlq` (Dead Letter Queue). Implement rate limiting, sequence checking, and duplicate detection. Own the Dockerfile, service health endpoint, and ingestion-level tests. |
| **Member 4** | **Route Management** | `services/route-service/` | Build the Route Management service with full CRUD operations for routes, stops, and geofences using **PostgreSQL + PostGIS**. Implement the **SQLAlchemy ORM models** for the `routes` schema (routes, stops, geofences tables). Expose REST endpoints: `GET /api/v1/routes`, `GET /api/v1/routes/{route_id}`, `GET /api/v1/routes/{route_id}/stops`. Serve route geometry (GeoJSON) for G3's map rendering. Own the Dockerfile and service-level tests. |
| **Member 5** | **Infrastructure + Simulator** | `docker/` + `scripts/` + `schemas/` | Expand `docker-compose.yml` to orchestrate the full Increment 1 stack: add Apache Flink (`jobmanager` + `taskmanager`), MQTT broker (Mosquitto), and configure network bridges between all services. Maintain the **shared Pydantic schemas** (`schemas/`). Enhance the **GPS Simulator** (`scripts/gps_simulator.py`) to emit realistic route-following telemetry. Own **database migration scripts** (`scripts/migrations/`), the `.env.example` configuration, and **integration tests** (`tests/integration/`) that verify the full end-to-end pipeline. |

##### Shared Resources (Everyone Uses, Member 5 Maintains)

These files are the **single source of truth** used across all services. Member 5 is the maintainer, but changes require team agreement.

| Shared Resource | Path | What It Contains | Who Reads It |
|----------------|------|-----------------|-------------|
| **GPS Schema** | `schemas/gps.py` | `GPSMessage` Pydantic model — the canonical GPS telemetry format | Member 2 (Flink input), Member 3 (validation), Member 1 (API responses) |
| **Bus Status Schema** | `schemas/bus_status.py` | `BusLifecycleState` enum, `BusStatusMessage` model | Member 1 (state transitions), Member 2 (Flink processing) |
| **Geo Config** | `schemas/geo_config.py` | `SRI_LANKA_BOUNDS` coordinate bounding box | Member 2 (Flink validation), Member 3 (ingestion validation) |
| **Schema Exports** | `schemas/__init__.py` | Centralized re-exports of all shared schemas | All members import from here |
| **Docker Compose** | `docker/docker-compose.yml` | Full infrastructure stack definition | All members (local dev environment) |
| **Environment Config** | `docker/.env.example` | Connection strings, ports, API keys template | All members (local setup) |
| **Root Requirements** | `requirements.txt` | Shared Python dependencies | All members |

##### Inter-Service Communication Contracts

Every arrow between services has a **defined contract**. If you change the format, you must notify the downstream member.

```
  G1 (MQTT)                Member 3                   Member 2                  Member 1
  ─────────               ──────────                  ──────────                ──────────
  GPS Device    ──MQTT──▶  Ingestion    ──AutoMQ──▶   Stream       ──Redis──▶  API Gateway
                           Service                    Processing               (WebSocket)
                                                         │
                                                         │──InfluxDB──▶ (time-series storage)
                                                         │
                           Member 4
                           ──────────
                           Route Mgmt   ──PostgreSQL──▶  (route geometry for deviation checks)
```

| Contract | Protocol | Topic / Channel | Payload Schema | Producer (Member) | Consumer (Member) |
|----------|----------|----------------|---------------|-------------------|-------------------|
| **MQTT → Ingestion** | MQTT 3.1.1 | `transport/bus/{busId}/location` | `GPSMessage` (from `schemas/gps.py`) | G1 (external) | Member 3 |
| **Ingestion → Flink** | AutoMQ (Kafka API) | `transport-telemetry-raw` | `GPSMessage` (JSON serialized) | Member 3 | Member 2 |
| **Ingestion → DLQ** | AutoMQ (Kafka API) | `transport-telemetry-dlq` | Raw invalid payload + error reason | Member 3 | (debug/monitoring) |
| **Flink → Gateway** | Redis Pub/Sub | Channel: `fleet:live` | `{busId, routeId, lat, lng, speed, heading, timestamp}` | Member 2 | Member 1 |
| **Flink → InfluxDB** | InfluxDB Line Protocol | Bucket: `telemetry` | `gps_readings` measurement | Member 2 | (historical queries) |
| **Gateway → Bus Status** | AutoMQ (Kafka API) | `bus.status` | `BusStatusMessage` (from `schemas/bus_status.py`) | Member 1 | Member 2 |
| **Route Geometry** | PostgreSQL (PostGIS) | Schema: `routes`, Tables: `routes`, `stops` | SQLAlchemy ORM models | Member 4 (writes) | Member 2 (reads for deviation checks), Member 1 (reads for API responses) |
| **Redis Cache** | Redis GET/SET | `bus:{bus_id}:position`, `bus:{bus_id}:status` | JSON position / status objects | Member 2 (writes) | Member 1 (reads) |

##### Cross-Member Coordination Rules

1. **Schema changes require a PR review from all affected members.** If Member 3 wants to add a field to `GPSMessage`, Members 1 and 2 must approve since they consume it.
2. **Each member writes their own unit tests** inside their service directory or in `tests/unit/{service-name}/`.
3. **Member 5 writes integration tests** in `tests/integration/` that spin up the full Docker stack and verify end-to-end data flow.
4. **Weekly sync:** All 5 members demo their service's current state every week. Contracts are validated during this sync.
5. **Database access:** Member 4 owns the `routes` schema. Member 1 reads from it (read-only). If Member 1 needs a new query, they request it from Member 4 or use the Route Service API.

#### Acceptance Criteria

- [ ] Simulated GPS appears on WebSocket within 2 seconds of emission
- [ ] Bus dot moves on G3 map (integration test with G3 team)
- [ ] Driver can change bus status via API and it reflects in live feed
- [ ] Driver delay reports are accepted and persisted via `POST /api/v1/driver/report-delay`
- [ ] Invalid GPS messages route to dead-letter topic (`transport-telemetry-dlq`)
- [ ] `/health` returns 200 with all dependency statuses

---

### Future Increments (2–5+)

> The following increments are **planned but not active** in the first release. They remain in the SRS v2.0 as the full product vision. Implementation starts after Increment 1 is stable.

<details>
<summary><strong>Increment 2: ETA Prediction Engine</strong> (Sprint 4–5)</summary>

**Goal:** Predict when buses arrive at stops using ML models.

| Component | Deliverable |
|-----------|------------|
| Feature Engineering | SRS v2.0 feature set: current speed, GPS coords, time-of-day (cyclic sin/cos encoding), day-of-week (0–6 integer), route segment ID, historical avg segment travel time (90-day rolling window), historical variance, crowd status (NOT_FULL=0 / SEMI_FULL=1 / FULL=2) |
| ETA Model | XGBoost regressor: urban + highway variants |
| Physics Fallback | `distance / speed` when ML unavailable |
| Geofencing | Kahathuduwa highway entrance/exit detection |
| ETA API | `GET /api/v1/eta/{bus_id}/{stop_id}` |
| Driver Delay Offset Application (FR-G2.5) | ETA engine applies additive offset to downstream ETAs using persisted delay reports submitted in Increment 1 |

**What users get:**
- Passenger taps a stop → sees "Bus arriving in ~4 min" with confidence
- Driver sees dynamic target time for next checkpoint

**Acceptance Criteria:**
- [ ] ETA prediction MAE < 90 seconds under normal operating conditions (NFR-P5)

</details>

<details>
<summary><strong>Increment 3: Trip Scheduling & Dispatch</strong> (Sprint 4–5)</summary>

**Goal:** Enable Scheduler to assign buses to departure slots. Driver reports availability.

| Component | Deliverable |
|-----------|------------|
| Departure Slot Grid | Pre-defined time slots per route |
| Bus Availability | Driver sets "Available in X minutes" |
| Dispatch Assignment | Scheduler assigns bus to next departure slot |
| Scheduling API | CRUD for slots, assignments |

> **Note:** This is where the system replaces the manual scheduling assumed in the first release.

</details>

<details>
<summary><strong>Increment 4: Anomaly Detection & Issue Reporting</strong> (Sprint 4–5)</summary>

**Goal:** Detect service disruptions automatically. Drivers report issues.

| Component | Deliverable |
|-----------|------------|
| Incremental 3-Layer Anomaly Detection | **Layer 1 (Inc 1):** Rule Engine — 3 deterministic rules (stationary bus, off-route deviation, communication loss). **Layer 2 (Inc 2):** Z-Score on speed/dwell-time. **Layer 3 (Inc 3/4):** Isolation Forest on multivariate features |
| Driver Incident Reporting (FR-G3.3) | `POST /api/v1/trips/{id}/incident` with codes: `BREAKDOWN`, `ACCIDENT`, `HEAVY_TRAFFIC`, `ROAD_CLOSURE`, `MEDICAL_EMERGENCY`. Transitions bus to `INCIDENT_REPORTED` state, fires admin alert |
| Admin Alert Management | `GET /api/v1/admin/alerts`, `POST /api/v1/admin/alerts/{id}/acknowledge` |

</details>

<details>
<summary><strong>Increment 5+: Route Search, Multi-Route, Crowd Intelligence</strong> (Sprint 6+)</summary>

**Goal:** Expand beyond single route. Let passengers search routes. Integrate crowd data from G1 IR sensors.

| Component | Deliverable |
|-----------|------------|
| GTFS Import | Seed multiple routes from GTFS feed |
| Route Search | Search by route number / destination |
| Crowd Data | IR sensor integration, occupancy bands |
| AI Scheduling | Auto-suggestions for dispatching extra buses |

</details>

---

## 4. Sprint-to-Increment Mapping

| Sprint | Dates (Approx.) | Increment | Key Deliverable |
|--------|-----------------|-----------|----------------|
| Sprint 1 | Week 1–2 | **Inc 0** | Docker stack, DB schemas, GPS simulator, CI, FastAPI skeleton |
| Sprint 2 | Week 3–4 | **Inc 1** | MQTT bridge, Flink basic cleaning, live feed |
| Sprint 3 | Week 5–6 | **Inc 1** | Driver status API, WebSocket feed, G3 integration test |
| Sprint 4 | Week 7–8 | **Inc 2 + 4** (parallel) | Feature eng. + ETA model / Anomaly L1+L3 |
| Sprint 5 | Week 9–10 | **Inc 2 + 3 + 4** (parallel) | ETA model / Scheduling API / Anomaly L2 + driver issues |
| Sprint 6+ | Week 11+ | **Inc 5+** | Route search, multi-route, crowd integration |

---

## 5. Definition of Done (per Increment)

An increment is "done" when:

- [ ] All acceptance criteria are met
- [ ] Unit test coverage ≥ 70% for new code
- [ ] API endpoints documented in Swagger (auto-generated by FastAPI)
- [ ] Docker image builds and passes health check
- [ ] Code reviewed and merged to `main`
- [ ] Sprint review demo completed

---

## 6. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| G1 delivers GPS data late | Medium | High | GPS simulator covers all G2 testing independently |
| Flink setup complexity | High | Medium | Start with simple Kafka consumers first; migrate to Flink in Inc 1 |
| ML model accuracy on small data | High | Medium | Physics fallback always available from first deployment |
| Cross-group integration issues | Medium | High | Contract-first design; weekly sync meetings with G1/G3/G4 |
| Scope creep from instructor feedback | Medium | Medium | Strict increment boundaries; changes go to next sprint |

---

## 7. Milestones

| Milestone | Target | Criteria |
|-----------|--------|----------|
| **M1: Infrastructure Ready** | End of Sprint 1 | Docker stack runs, CI passes, GPS simulator works, `/health` returns 200 |
| **M2: First Bus on Map** | End of Sprint 3 | Simulated bus visible on G3 map via WebSocket |
| **M3: ETA Working** | End of Sprint 5 | Tap a stop, see ETA with confidence score |
| **M4: Anomaly Alerts** | End of Sprint 5 | Driver reports breakdown, alert created |
| **M5: Full Demo Ready** | End of Sprint 7 | All active user roles have working flows for demo |

---

*Last updated: 19th April 2026*
