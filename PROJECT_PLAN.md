# OnTime G2 — Project Plan & Incremental Delivery Roadmap

> **Version:** 1.1  
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
| **Bus state machine is the backbone** | Every feature depends on tracking bus state: `IDLE → WAITING_AT_DEPOT → DEPARTED_ORIGIN → EN_ROUTE → ARRIVED_DESTINATION → IDLE`. |
| **No Flink in Increment 0** | Stream processing (Flink) is introduced in Increment 1. Increment 0 sets up infra only (Kafka, PostgreSQL, Redis). |
| **GPS Simulator replaces G1 hardware** | Until G1 delivers real GPS devices, we use a Python simulator that emits fake 1 Hz GPS data to Kafka. |

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
| **Docker Compose** | Dev stack: Kafka + Zookeeper, PostgreSQL + PostGIS, Redis |
| **Database Schemas** | SQL scripts for all tables (routes, stops, buses, gps_readings, trips, etc.) |
| **Route Seeding** | Script to seed Moratuwa → Kadawatha route geometry + 20+ stops into PostGIS |
| **GPS Simulator** | Python script that publishes fake GPS at 1 Hz to `gps.raw` Kafka topic |
| **CI Pipeline** | GitHub Actions: lint (ruff), type check (mypy), test (pytest), Docker build |
| **FastAPI Skeleton** | `/health` and `/metrics` endpoints, Pydantic models for GPS + bus status schemas |
| **Dev Config** | `.env.example` with local + Neon cloud DB URLs, Docker networking |

#### 5-Member Task Distribution

| Member | Role | What They Own | Key Deliverables |
|--------|------|--------------|-----------------|
| **Member 1** | Infrastructure & Docker Lead | Docker environment | `docker/docker-compose.yml` (Kafka, Zookeeper, PG+PostGIS, Redis), `docker/.env.example`, health check wait scripts, Docker networking config |
| **Member 2** | Database & Schema Lead | All database schemas | SQL migration scripts in `scripts/migrations/`, schema for all tables (routes, stops, buses, gps_readings, trips, stop_arrivals, anomalies, geofences), Neon cloud DB setup for team access, local PG+PostGIS config |
| **Member 3** | Data Seeding & Simulator Lead | Test data + GPS simulator | `scripts/seed_routes.py` (Moratuwa→Kadawatha route + 20+ stops with PostGIS LINESTRING/POINT geometry), `scripts/gps_simulator.py` (publishes fake 1 Hz GPS JSON to Kafka `gps.raw` topic) |
| **Member 4** | CI/CD & Quality Lead | Pipeline + test framework | `.github/workflows/ci.yml` (ruff lint + mypy type check + pytest + Docker build), `tests/` directory structure with conftest.py, PR template, branch protection rules, `pyproject.toml` with tool configs |
| **Member 5** | Interface & Integration Lead | API skeleton + glue | `services/api-gateway/` FastAPI app with `/health` + `/metrics`, Pydantic models (`schemas/gps.py`, `schemas/bus_status.py`), project-wide folder structure, integration test that verifies: docker up → seed → simulate → health OK |

> **Member 5 is the glue person.** They define the project skeleton that everyone else plugs into. They also write the end-to-end integration test that chains all other members' work together.

#### How Members Collaborate

```
Member 1 (Docker)          Member 2 (DB Schemas)
     │                          │
     │  docker compose up       │  SQL migration scripts
     │  provides running        │  run against PG container
     │  PG + Kafka + Redis      │  from Member 1
     └──────────┬───────────────┘
                │
     Member 3 (Seeding + Simulator)
                │
     seed_routes.py writes to PG (Member 2's schema)
     gps_simulator.py publishes to Kafka (Member 1's container)
                │
     Member 4 (CI/CD)
                │
     GitHub Actions runs all of the above + linting
                │
     Member 5 (Integration)
                │
     FastAPI reads from PG + Redis
     Integration test chains everything together
```

#### Database Setup: Local + Cloud

The project uses **two database options** via a single `.env.example`:

| Option | When to Use | Setup |
|--------|-------------|-------|
| **Local PostgreSQL** (Docker) | Solo development, testing, CI | Automatically starts via `docker compose up`. Connection: `postgresql://ontime:ontime@localhost:5432/ontime` |
| **Neon Cloud PostgreSQL** | Team collaboration, shared data | Team lead creates Neon project, shares connection URL privately. Connection: `postgresql://user:pass@ep-xxx.neon.tech/ontime?sslmode=require` |

Members set the active `DATABASE_URL` in their local `.env` file (never committed to git).

#### Acceptance Criteria

- [ ] `docker compose up` brings up Kafka + PostgreSQL + Redis with zero errors
- [ ] `python scripts/seed_routes.py` populates route + 20 stops in PostGIS
- [ ] `python scripts/gps_simulator.py` publishes GPS messages to `gps.raw` Kafka topic
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
| **Ingestion Service** | MQTT → Kafka bridge; Pydantic validation; DLQ routing for invalid GPS |
| **Stream Processing** | Flink job: Kalman filter + bounding box check (no feature extraction yet) |
| **Bus State Machine** | `IDLE → WAITING_AT_DEPOT → DEPARTED_ORIGIN → EN_ROUTE → ARRIVED_DESTINATION → IDLE` |
| **Driver Status API** | `POST /api/v1/bus/{bus_id}/status` — driver taps to change state |
| **Live Feed** | `WS /ws/live-feed` — 1-second fleet status push to G3 |
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
- [ ] Invalid GPS messages route to dead-letter topic (`gps.dlq`)
- [ ] `/health` returns 200 with all dependency statuses

---

### Future Increments (2–5+)

> The following increments are **planned but not active** in the first release. They remain in the SRS v1.1 as the full product vision. Implementation starts after Increment 1 is stable.

<details>
<summary><strong>Increment 2: ETA Prediction Engine</strong> (Sprint 4–5)</summary>

**Goal:** Predict when buses arrive at stops using ML models.

| Component | Deliverable |
|-----------|------------|
| Feature Engineering | 16-feature extraction in Flink pipeline |
| ETA Model | XGBoost regressor: urban + highway variants |
| Physics Fallback | `distance / speed` when ML unavailable |
| Geofencing | Kahathuduwa highway entrance/exit detection |
| ETA API | `GET /api/v1/eta/{bus_id}`, `GET /api/v1/eta/{bus_id}/{stop_id}` |

**What users get:**
- Passenger taps a stop → sees "Bus arriving in ~4 min" with confidence
- Driver sees dynamic target time for next checkpoint

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
| 3-Layer Anomaly Detection | Statistical + ML (Isolation Forest) + Rule engine |
| Driver Issue Reporting | `POST /bus/{bus_id}/issue` with enum types |
| Trip Termination | Driver taps "Terminate" → bus removed from fleet |

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

## 5. Team Allocation — Increment 0 (Sprint 1)

| Member | Primary Role | Key Outputs |
|--------|-------------|-------------|
| **Member 1** | Infrastructure & Docker Lead | `docker-compose.yml`, container networking, health scripts |
| **Member 2** | Database & Schema Lead | SQL migrations, Neon cloud setup, PostGIS config |
| **Member 3** | Data Seeding & Simulator Lead | `seed_routes.py`, `gps_simulator.py` |
| **Member 4** | CI/CD & Quality Lead | GitHub Actions, test framework, PR template |
| **Member 5** | Interface & Integration Lead | FastAPI skeleton, Pydantic models, integration test |

**For Increment 1+ allocation**, see [STRATEGY.md](STRATEGY.md) Section 2.

---

## 6. Definition of Done (per Increment)

An increment is "done" when:

- [ ] All acceptance criteria are met
- [ ] Unit test coverage ≥ 70% for new code
- [ ] API endpoints documented in Swagger (auto-generated by FastAPI)
- [ ] Docker image builds and passes health check
- [ ] Code reviewed and merged to `main`
- [ ] Sprint review demo completed

---

## 7. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| G1 delivers GPS data late | Medium | High | GPS simulator covers all G2 testing independently |
| Flink setup complexity | High | Medium | Start with simple Kafka consumers first; migrate to Flink in Inc 1 |
| ML model accuracy on small data | High | Medium | Physics fallback always available from first deployment |
| Cross-group integration issues | Medium | High | Contract-first design; weekly sync meetings with G1/G3/G4 |
| Scope creep from instructor feedback | Medium | Medium | Strict increment boundaries; changes go to next sprint |

---

## 8. Milestones

| Milestone | Target | Criteria |
|-----------|--------|----------|
| **M1: Infrastructure Ready** | End of Sprint 1 | Docker stack runs, CI passes, GPS simulator works, `/health` returns 200 |
| **M2: First Bus on Map** | End of Sprint 3 | Simulated bus visible on G3 map via WebSocket |
| **M3: ETA Working** | End of Sprint 5 | Tap a stop, see ETA with confidence score |
| **M4: Anomaly Alerts** | End of Sprint 5 | Driver reports breakdown, alert created |
| **M5: Full Demo Ready** | End of Sprint 7 | All active user roles have working flows for demo |

---

*Last updated: 16-th April 2026*
