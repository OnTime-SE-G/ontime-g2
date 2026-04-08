# OnTime G2 — Project Plan & Incremental Delivery Roadmap

> **Version:** 1.0  
> **Date:** April 2026  
> **Methodology:** Agile Scrum (2-week sprints)  
> **Status:** Planning

---

## 1. Incremental Strategy Overview

The system is delivered in **6 modular increments**. Each increment produces a **fully working software version** that adds value without breaking existing functionality. Increments 2, 3, and 4 are **parallel-capable** — different team members or subgroups can work on them simultaneously once Increment 1 is stable.

```
                    ┌──────────────────────┐
                    │   Increment 0        │
                    │   Foundation Infra    │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Increment 1        │
                    │   GPS + Live Map     │
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
                    │   Increment 5        │
                    │   Route Search &     │
                    │   Multi-Route        │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │   Increment 6        │
                    │   Crowd Intelligence │
                    │   & AI Optimization  │
                    └──────────────────────┘
```

> **Key design principle:** Each increment maps to one or more independent microservices. No increment requires a complete rewrite of a previous one.

---

## 2. Increment Details

---

### Increment 0: Foundation Infrastructure

**Goal:** Establish the base platform so all subsequent services can be built and deployed.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 1 (2 weeks) |
| **Dependency** | None |
| **Services Built** | Docker Compose stack, database schemas, CI pipeline skeleton |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **Docker Compose** | Full dev stack: Kafka, Zookeeper, PostgreSQL + PostGIS, Redis |
| **Database** | Schema creation scripts for all tables (routes, stops, buses, gps_readings, etc.) |
| **Route Seeding** | Script to seed Moratuwa → Kadawatha route geometry + 20+ stops |
| **GPS Simulator** | Python script that emits fake GPS at 1 Hz for testing |
| **CI Pipeline** | GitHub Actions: lint (ruff), type check (mypy), test (pytest), build Docker |
| **Dev Config** | `.env.example`, Docker networking, VS Code devcontainer (optional) |

#### Per-Role Impact

| Role | What they get |
|------|--------------|
| Passenger | Nothing yet (no UI) |
| Driver | Nothing yet (no UI) |
| Scheduler | Nothing yet (no UI) |

#### Acceptance Criteria

- [ ] `docker compose up` brings up Kafka + PostgreSQL + Redis with zero errors
- [ ] `python scripts/seed_routes.py` populates route + stops in PostGIS
- [ ] `python scripts/gps_simulator.py` publishes GPS messages to Kafka topic
- [ ] GitHub Actions runs lint + tests on every push

---

### Increment 1: GPS Pipeline & Live Tracking

**Goal:** Prove that data flows end-to-end from GPS device to a live map.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 2–3 (4 weeks) |
| **Dependency** | Increment 0 infrastructure |
| **Services Built** | Ingestion Service, Stream Processing (basic), API Gateway (basic) |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **Ingestion Service** | MQTT → Kafka bridge (`mqtt_bridge.py`); Pydantic validation; DLQ routing |
| **Stream Processing** | Flink job: Kalman filter + bounding box check (no feature extraction yet) |
| **API Gateway** | `GET /health`, `GET /api/v1/routes`, `GET /api/v1/routes/{id}/buses`, `WS /ws/live-feed` |
| **Bus State Machine** | Basic states: `IDLE → DEPARTED → EN_ROUTE → ARRIVED → IDLE` |
| **Driver Status API** | `POST /api/v1/bus/{bus_id}/status` — driver taps to change state |

#### Per-Role Impact

| Role | What they get |
|------|--------------|
| **Passenger** | Opens map → sees route line drawn → sees bus dots moving in real-time |
| **Driver** | Logs in with bus credentials → taps **Start Trip** / **End Trip** (big buttons) |
| **Scheduler** | Web dashboard → sees map with all active buses as moving dots |

#### Acceptance Criteria

- [ ] Simulated GPS appears on WebSocket within 2 seconds of emission
- [ ] Bus dot moves on G3 map (integration test with G3)
- [ ] Driver can change bus status via API and it reflects in live feed
- [ ] Invalid GPS messages route to dead-letter topic
- [ ] `/health` returns 200 with all dependency statuses

---

### Increment 2: ETA Prediction Engine

**Goal:** Add time intelligence — predict when buses arrive at stops.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 4–5 (4 weeks) |
| **Dependency** | Increment 1 (GPS data flowing) |
| **Services Built** | ETA Prediction Service, enhanced Stream Processing |
| **Parallel With** | Increments 3 and 4 |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **Feature Engineering** | 16-feature extraction in Flink pipeline (see SRS Section 7.2) |
| **ETA Model** | XGBoost regressor: urban variant + highway variant |
| **Physics Fallback** | `distance_remaining / effective_speed` when ML unavailable |
| **Geofencing** | Kahathuduwa highway entrance/exit detection; model variant switch |
| **ETA API** | `GET /api/v1/eta/{bus_id}`, `GET /api/v1/eta/{bus_id}/{stop_id}` |
| **Model Training** | `scripts/train_models.py` for batch retraining |
| **MLflow Integration** | Experiment tracking, model versioning |

#### Per-Role Impact

| Role | What they get |
|------|--------------|
| **Passenger** | Taps a bus stop → sees ETA (e.g., "Bus 138 arriving in ~4 min") with confidence |
| **Driver** | Sees dynamic target time for next checkpoint (ETA-based, not static timetable) |
| **Scheduler** | Dashboard now shows ETA data alongside bus positions |

#### Acceptance Criteria

- [ ] ETA prediction returns within 100ms (p95)
- [ ] Model switches from urban → highway at Kahathuduwa geofence
- [ ] Physics fallback activates when model confidence < 0.5
- [ ] ETA updates every ~5 seconds per bus
- [ ] MLflow logs training runs with metrics

---

### Increment 3: Trip Scheduling & Dispatch

**Goal:** Enable the Scheduler to assign buses to departure slots and drivers to report availability.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 4–5 (4 weeks) |
| **Dependency** | Increment 1 (bus status tracking) |
| **Services Built** | Scheduling Service |
| **Parallel With** | Increments 2 and 4 |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **Departure Slot Grid** | Pre-defined time slots per route (e.g., every 15 min from 05:00–22:00) |
| **Bus Availability** | Driver marks trip-level availability: "Available in 30 min" after a trip |
| **Dispatch Assignment** | Scheduler assigns an available bus to the next departure slot |
| **Scheduling API** | CRUD for slots, assignments; `GET /api/v1/schedule/{route_id}` |
| **Scheduling Dashboard** | Web view: idle buses list + next 1 departure slot assignment (MVP: next 1 only) |

#### Per-Role Impact

| Role | What they get |
|------|--------------|
| **Passenger** | Can see when the next bus is **scheduled** to depart (separate from live ETA) |
| **Driver** | After ending a trip → sets "Available in X minutes" → appears in Scheduler's pool |
| **Scheduler** | Views idle buses → assigns one to the next open departure slot on a route |

#### Business Rules (MVP)

- Scheduler can only assign the **next upcoming** departure slot per route (not 3 ahead — simplified for first increment)
- A bus cannot be assigned if its availability window hasn't started
- Only one bus per departure slot

#### Acceptance Criteria

- [ ] Scheduler can view departure slot grid for a route
- [ ] Scheduler can assign a bus from the "available" pool to a slot
- [ ] Driver can set availability window after trip completion
- [ ] Passenger can query scheduled departures for a route
- [ ] Double-booking a slot returns 409 Conflict

---

### Increment 4: Anomaly Detection & Issue Reporting

**Goal:** Detect service disruptions automatically and let drivers report issues.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 4–5 (4 weeks) |
| **Dependency** | Increment 1 (GPS data flowing) |
| **Services Built** | Anomaly Detection Service, Driver Issue Reporting |
| **Parallel With** | Increments 2 and 3 |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **Anomaly Layer 1** | Statistical Z-score on speed, dwell, heading (5-min rolling window) |
| **Anomaly Layer 2** | Isolation Forest on 16-feature vectors |
| **Anomaly Layer 3** | Rule engine: off-route, long stop, GPS loss, speed violation, geofence exit |
| **Result Aggregator** | Weighted voting → unified anomaly record with confidence |
| **Driver Issue API** | `POST /api/v1/bus/{bus_id}/issue` with enum: `BREAKDOWN`, `ACCIDENT`, `HEAVY_TRAFFIC`, `ROAD_BLOCKED`, `WEATHER`, `OTHER` |
| **Bus Termination** | Driver taps "Terminate Trip" → bus status = TERMINATED; event published |
| **Anomaly API** | `GET /api/v1/anomalies/active`, `GET /api/v1/anomalies/{bus_id}` |

#### Per-Role Impact

| Role | What they get |
|------|--------------|
| **Passenger** | Sees delay indicator on affected buses (in-app only) |
| **Driver** | Can report issues via big-button UI: `Breakdown` / `Traffic` / `Other` |
| **Scheduler** | Dashboard shows anomaly alerts; terminated buses highlighted in red |

#### Deferred to Later

- Auto-detect bus stopped >10 min → AI popup for driver (Increment 6)
- Scheduler receives dispatch alert on termination to assign replacement (Increment 5+)

#### Acceptance Criteria

- [ ] Anomaly alert fires within 5 seconds of triggering condition
- [ ] Driver issue report creates anomaly record + updates bus status
- [ ] Terminated bus disappears from active fleet and Scheduler gets notified
- [ ] Resolved anomalies are automatically cleared
- [ ] Anomaly records persisted with PostGIS location

---

### Increment 5: Route Search & Multi-Route Support

**Goal:** Expand beyond single route. Let passengers search and discover routes.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 6–7 (4 weeks) |
| **Dependency** | Increment 1 (basic route display) |
| **Services Built** | Route Management Service (enhanced) |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **GTFS Import** | Script to import route geometry and stops from GTFS feed |
| **Route Search API** | `GET /api/v1/routes/search?q={query}` — search by route number, origin, destination |
| **Direction Model** | Each route has two direction variants (outbound/inbound) with distinct colors |
| **Multi-Route Map** | Map shows all route lines (bus routes in grey, selected route in blue/green) |
| **Nearest Route** | If location enabled: `GET /api/v1/routes/nearest?lat=X&lng=Y` → nearest routes + stops |

#### Per-Role Impact

| Role | What they get |
|------|--------------|
| **Passenger** | Search routes by number/destination → route highlights on map → direction swap → see ETAs for selected route |
| **Driver** | Route assignment shown; no search needed |
| **Scheduler** | Dashboard now filterable by route |

#### Acceptance Criteria

- [ ] GTFS import seeds 5+ routes successfully
- [ ] Search by route number returns correct route with stops
- [ ] Search by destination returns routes passing through that area
- [ ] Direction swap toggles blue ↔ green route rendering
- [ ] Nearest route API returns routes within 500m of given coordinates

---

### Increment 6: Crowd Intelligence & AI Optimization (Future)

**Goal:** Integrate IoT crowd data and introduce AI-driven scheduling.

| Aspect | Details |
|--------|---------|
| **Duration** | Sprint 8+ (ongoing) |
| **Dependency** | Increment 3 (scheduling) + G1 IR sensor hardware |
| **Services Built** | Crowd Processing Module, AI Scheduling Advisor |

#### Scope

| Component | Deliverable |
|-----------|------------|
| **G1 IR Sensor Integration** | MQTT topic for crowd count: `bus/{bus_id}/occupancy` (TBD with G1) |
| **Crowd Band** | Occupancy classification: Green (Seats Available), Yellow (Standing Only), Red (Full) |
| **Crowd Prediction** | ML model: predict crowd level at each stop based on historical patterns + current bus load |
| **Auto-Stuck Detection** | Bus not moving for 10+ min → AI popup: "Are you stuck?" → driver selects reason |
| **AI Schedule Suggestions** | Based on crowd at stops → suggest dispatching extra buses |
| **Scheduler 3-Slot Horizon** | Upgrade from next-1 to next-3 departure slot planning |

#### Per-Role Impact

| Role | What they get |
|------|--------------|
| **Passenger** | Crowd indicator on approaching bus (Green/Yellow/Red); predicted crowd at their stop |
| **Driver** | Auto-prompt when stuck; voice-friendly interaction |
| **Scheduler** | AI suggests "Send Bus X to Route Y — high crowd at Stop Z"; can accept/reject |

#### Status

> ⚠️ **Blocked on G1 IR sensor implementation.** Interface contract to be defined.

---

## 3. Sprint-to-Increment Mapping

| Sprint | Dates (Approximate) | Increment | Key Deliverable |
|--------|---------------------|-----------|----------------|
| Sprint 1 | Week 1–2 | **Inc 0** | Docker stack, DB schemas, GPS simulator, CI |
| Sprint 2 | Week 3–4 | **Inc 1** | MQTT bridge, Flink basic cleaning, live feed |
| Sprint 3 | Week 5–6 | **Inc 1** | Driver status API, WebSocket feed, integration test |
| Sprint 4 | Week 7–8 | **Inc 2 + 3 + 4** (parallel) | Feature eng. / Scheduling API / Anomaly L1+L3 |
| Sprint 5 | Week 9–10 | **Inc 2 + 3 + 4** (parallel) | ETA model / Dispatch UI / Anomaly L2 + driver issues |
| Sprint 6 | Week 11–12 | **Inc 5** | GTFS import, route search, multi-route, direction swap |
| Sprint 7 | Week 13–14 | **Inc 5** + Polish | Nearest route, integration testing, docs |
| Sprint 8+ | Week 15+ | **Inc 6** (if time) | Crowd integration, AI suggestions |

---

## 4. Team Allocation Strategy

For a team of 5 G2 members, the recommended allocation during the parallel sprint phase (Sprints 4–5):

| Member | Primary Focus | Secondary Focus |
|--------|--------------|-----------------|
| **Member 1** | ETA Prediction Service (Inc 2) | MLflow integration |
| **Member 2** | Feature Engineering in Flink (Inc 2) | Geofencing logic |
| **Member 3** | Scheduling Service (Inc 3) | Database schema |
| **Member 4** | Anomaly Detection Service (Inc 4) | Driver issue API |
| **Member 5** | API Gateway + Integration Testing | WebSocket optimization |

---

## 5. Definition of Done (per Increment)

An increment is "done" when:

- [ ] All acceptance criteria are met
- [ ] Unit test coverage ≥ 70% for new code
- [ ] API endpoints documented in Swagger (auto-generated by FastAPI)
- [ ] Integration test with G3 passes (bus appears on map / ETA shows / etc.)
- [ ] Docker image builds and passes health check
- [ ] Code reviewed and merged to `main`
- [ ] Sprint review demo completed

---

## 6. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| G1 delivers GPS data late | Medium | High | GPS simulator covers all G2 testing |
| Flink setup complexity | High | Medium | Start with simple Kafka consumers; migrate to Flink |
| ML model accuracy on small data | High | Medium | Physics fallback always available |
| Cross-group integration issues | Medium | High | Contract-first design; weekly integration syncs |
| Scope creep from instructor feedback | Medium | Medium | Strict increment boundaries; changes go to next sprint |

---

## 7. Milestones

| Milestone | Target | Criteria |
|-----------|--------|----------|
| **M1: Infrastructure Ready** | End of Sprint 1 | Docker stack runs, CI passes, GPS simulator works |
| **M2: First Bus on Map** | End of Sprint 3 | Simulated bus visible on G3 map via WebSocket |
| **M3: ETA Working** | End of Sprint 5 | Tap a stop, see ETA with confidence score |
| **M4: Scheduler Dispatches** | End of Sprint 5 | Scheduler assigns bus to departure slot |
| **M5: Anomaly Alerts** | End of Sprint 5 | Driver reports breakdown, Scheduler sees alert |
| **M6: Multi-Route Search** | End of Sprint 7 | Passenger searches route 138, sees it highlighted |
| **M7: Full Demo Ready** | End of Sprint 7 | All 3 user roles have working flows for demo |

---

*Last updated: April 2026*
