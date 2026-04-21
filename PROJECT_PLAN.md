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

### Increment 0: Foundation Infrastructure

**Goal:** Set up the base platform so all subsequent services can be built and deployed. Every team member should be able to `docker compose up` and have a working Dev environment.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 1 (2 weeks) |
| **Dependency** | None |
| **Deliverables** | Docker Compose stack, DB schemas, route seeding, GPS simulator, CI pipeline, FastAPI skeleton |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **Docker Compose** | Dev stack: AutoMQ (or Kafka fallback), PostgreSQL + PostGIS, InfluxDB, Redis |
| **Database Schemas** | SQL scripts for all PG tables, and initialization for InfluxDB buckets |
| **Route Seeding** | Script to seed Moratuwa → Kadawatha route geometry + 20+ stops into PostGIS |
| **GPS Simulator** | Python script that publishes fake GPS every 3–5 seconds to `transport-telemetry-raw` AutoMQ topic |
| **CI Pipeline** | GitHub Actions: lint (ruff), type check (mypy), test (pytest), Docker build |
| **FastAPI Skeleton** | `/health` and `/metrics` endpoints, Pydantic models for GPS + bus status schemas |
| **Dev Config** | `.env.example` with local + Cloud DB URLs (Neon PG + InfluxDB Cloud), Docker networking |

#### 5-Member Task Distribution

| Member | Role | What They Own | Key Deliverables |
|--------|------|--------------|-----------------|
| **Janidu** | Infrastructure & Docker Lead | Docker environment | `docker/docker-compose.yml` (Kafka/AutoMQ, PG+PostGIS, InfluxDB, Redis), `docker/.env.example`, health check wait scripts, Docker networking config |
| **Kusal** | Database & Schema Lead | All database schemas | SQL migration scripts in `scripts/migrations/`, schema for all PG tables (routes, stops, buses, trips, stop_arrivals, anomalies, geofences) + InfluxDB telemetry schemas, Neon/InfluxDB cloud DB setup for team access, local config |
| **Chamodh** | Data Seeding & Simulator Lead | Test data + GPS simulator | `scripts/seed_routes.py` (Moratuwa→Kadawatha route + 20+ stops with PostGIS LINESTRING/POINT geometry), `scripts/gps_simulator.py` (publishes fake GPS JSON every 3–5 seconds to AutoMQ `transport-telemetry-raw` topic) |
| **Nidharshan** | CI/CD & Quality Lead | Pipeline + test framework | `.github/workflows/ci.yml` (ruff lint + mypy type check + pytest + Docker build), `tests/` directory structure with conftest.py, PR template, branch protection rules, `pyproject.toml` with tool configs |
| **Nathasha** | Interface & Integration Lead | API skeleton + glue | `services/api-gateway/` FastAPI app with `/health` + `/metrics`, Pydantic models (`schemas/gps.py`, `schemas/bus_status.py`), project-wide folder structure, integration test that verifies: docker up → seed → simulate → health OK |

> **Nathasha is the glue person.** She defines the project skeleton that everyone else plugs into. She also writes the end-to-end integration test that chains all other members' work together.

#### How Members Collaborate

```
Janidu (Docker)             Kusal (DB Schemas)
     │                          │
     │  docker compose up       │  SQL migration scripts
     │  provides running        │  run against PG + Influx
     │  PG + Influx + AutoMQ    │  containers from Janidu
     └──────────┬───────────────┘
                │
     Chamodh (Seeding + Simulator)
                │
     seed_routes.py writes to PG (Kusal's schema)
     gps_simulator.py publishes to AutoMQ (Janidu's container)
                │
     Nidharshan (CI/CD)
                │
     GitHub Actions runs all of the above + linting
                │
     Nathasha (Integration)
                │
     FastAPI reads from PG + Redis
     Integration test chains everything together
```

#### Database Setup: Local + Cloud

The project uses **two database options** via a single `.env.example`:

| Option | When to Use | Setup |
|--------|-------------|-------|
| **Local DBs (Docker)** | Solo development, testing, CI | Automatically starts via `docker compose up`. Connections: PG (`localhost:5432`), InfluxDB (`localhost:8086`) |
| **Team Cloud DBs** | Team collaboration, shared data | Team lead creates Neon PG + InfluxDB Cloud projects, shares connection URLs privately.  |

Members set the active `DATABASE_URL` in their local `.env` file (never committed to git).

#### Acceptance Criteria

- [ ] `docker compose up` brings up AutoMQ/Kafka + PostgreSQL + InfluxDB + Redis with zero errors
- [ ] `python scripts/seed_routes.py` populates route + 20 stops in PostGIS
- [ ] `python scripts/gps_simulator.py` publishes GPS messages to `transport-telemetry-raw` AutoMQ topic
- [ ] `curl localhost:8000/health` returns 200 with dependency statuses
- [ ] GitHub Actions runs lint + type check + tests on every push and passes

---

### Increment 1: GPS Pipeline & Live Tracking + Bus State Machine

**Goal:** Prove that data flows end-to-end from GPS to a live map. Driver can start/end trips. Passenger sees buses moving.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 2–3 (4 weeks) |
| **Dependency** | Increment 0 infrastructure |
| **Services Built** | Ingestion Service, Stream Processing (basic Flink), API Gateway (enhanced) |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **Ingestion Service** | MQTT → AutoMQ bridge; Pydantic validation; DLQ routing for invalid GPS. *Note: G1 calculates speed and heading locally on the node.* |
| **Stream Processing** | Flink job: Kalman filter + bounding box check (no feature extraction yet) |
| **Bus State Machine** | `WAITING_AT_DEPOT → DEPARTED_ORIGIN → EN_ROUTE → ARRIVED_DESTINATION` (↕ `INCIDENT_REPORTED` from `EN_ROUTE`, admin reset: `ARRIVED_DESTINATION → WAITING_AT_DEPOT`) |
| **Driver Status API** | `POST /api/v1/trips/{id}/state` - driver taps to change trip state; `POST /api/v1/driver/start-trip` - driver starts trip |
| **Driver Delay Reporting (FR-G2.5)** | `POST /api/v1/driver/report-delay` - driver submits delay reason (`TRAFFIC`, `BREAKDOWN`, `ACCIDENT`, `OTHER`) + estimated minutes; persisted for ETA offset processing in Increment 2 |
| **Live Feed** | `WS wss://api.ontime.lk/v1/live` - delta updates (~every 3-5s per active bus), full state on first connect |
| **Route API** | `GET /api/v1/routes`, `GET /api/v1/routes/{id}/buses` |

#### What Each Role Gets

| Role | Experience |
|------|-----------|
| **Passenger** | Opens map → sees route line → sees bus dots moving in real-time |
| **Driver** | Logs in with bus credentials → taps **Start Trip** / **End Trip** → bus state changes flow to system |

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
