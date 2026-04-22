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

#### 5-Member Task Distribution (G2 Only)

| Member | Focus Layer       | Increment 1 Responsibilities |
|--------|-------------------|------------------------------|
| **Member 1** | Infrastructure | Expand orchestration: Add Apache Flink (`jobmanager` and `taskmanager`) to `docker-compose.yml`. Manage environment variables and network bridges for the new cluster. |
| **Member 2** | Database Layer | Build the SQLAlchemy ORM layer. Connect the Python microservices natively to PostgreSQL and implement the Redis caching schemas. |
| **Member 3** | Ingestion Layer | Develop the **Ingestion Service**. This service bridges G1's MQTT hardware signals securely into our AutoMQ `transport-telemetry-raw` topic. |
| **Member 4** | Processing Layer| Lead the Apache Flink development. Write the PyFlink stream processing job that consumes raw GPS from AutoMQ, cleans it, and publishes it back to Redis. |
| **Member 5** | API Layer (Gateway)| Engineer the strict 3-Layer backend (`routers`, `services`, `models`). Implement the **Mathematical ETA Stub** inside the models layer. Connect the `live` WebSocket natively to Redis Pub/Sub. |

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
