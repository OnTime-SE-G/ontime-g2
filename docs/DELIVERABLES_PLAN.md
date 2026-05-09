# OnTime — Project Deliverables Plan (Group G)

> **Purpose:** Track all 10 report deliverables + demo requirements. Maps each deliverable to the responsible group(s) and breaks down G2's specific contributions.
> **Last updated:** 26th April 2026

---

## 1. Who Makes What — Group Responsibility Matrix

### Quick Reference

| Group | Primary Focus | What They Write In The Report |
|-------|-------------|-------------------------------|
| **G1** | Device & Edge (IoT) | Hardware design, GPS module specs, MQTT protocol, edge filtering, sensor integration, device lifecycle |
| **G2** | Data & Intelligence | Stream architecture, Kafka pipeline, data validation, ML model design (ETA/anomaly), algorithms, data models |
| **G3** | System Eng & Interaction | UI/UX design, mobile app architecture, map integration, notification system, user flows |
| **G4** | Platform, Security & Integration | CI/CD, Kubernetes, Kong API gateway, Keycloak auth, Prometheus/Grafana, security testing, deployment |

### Per-Deliverable Breakdown

| # | Deliverable | Lead Group | G1 Writes | G2 Writes | G3 Writes | G4 Writes |
|---|------------|-----------|-----------|-----------|-----------|-----------|
| 1 | **SRS** | **G2** ✅ Done | Hardware requirements, device constraints | Functional reqs (FR-G2.*), NFR, domain model | User stories, UI requirements | Security requirements, NFR |
| 2 | **Design Spec** | **All** | Edge device architecture, circuit diagrams, firmware design | Microservices architecture, Kafka topic design, DB schema (PostGIS, InfluxDB), event flow diagrams | Mobile app architecture, UI wireframes, component design | Deployment architecture, K8s manifests, network topology |
| 3 | **Dev Details** | **G2** | — | Ingestion pipeline code, Flink jobs, validation algorithms, ETA heuristic, data models (Pydantic schemas, SQLAlchemy ORM) | — | — |
| 4 | **Testing** | **All** | Device testing, signal quality tests | Unit tests (pytest), integration tests, load tests (locust), data validation tests | UI testing, usability testing, UAT | Security pen testing, chaos testing, performance testing |
| 5 | **Deployment** | **G4** | Device provisioning, OTA plan | Dockerfile per service, docker-compose, env config | App store deployment plan | K8s manifests, Helm charts, ArgoCD, Terraform, CI/CD pipeline |
| 6 | **Project Mgmt** | **All** | Sprint evidence for G1 tasks | Sprint boards, burndown charts, standup notes, retrospectives | Sprint evidence for G3 tasks | Sprint evidence for G4 tasks |
| 7 | **Work Estimation** | **All** | G1 task estimates | Story points, velocity tracking, task breakdown per member | G3 task estimates | G4 task estimates |
| 8 | **User Training** | **G3** | Device installation guide | API documentation (Swagger auto-generated) | User manual, training materials, help docs | System admin guide |
| 9 | **Evolution Plan** | **All** | Hardware upgrade path | ML model retraining plan, schema versioning, API versioning strategy | Feature roadmap, UI evolution | Infrastructure scaling plan, migration strategies |
| 10 | **Individual Reports** | **Individual** | 2 pages each (5 students) | 2 pages each (5 students) | 2 pages each (5 students) | 2 pages each (5 students) |

---

## 2. G2 Detailed Deliverable Plan

### What G2 Must Produce for the Report

#### Deliverable 2: Design Specification (G2's Section)

| What to document | Source | Status |
|-----------------|--------|--------|
| Microservices architecture diagram | `STRATEGY.md` Section 2 | 🟡 Written, needs formatting for report |
| Service catalog (ports, topics, responsibilities) | `STRATEGY.md` Section 2.2 | 🟡 Written |
| Bus state machine diagram | `STRATEGY.md` Section 2.5 | 🟡 Written |
| Kafka/AutoMQ topic design + message guarantees | `STRATEGY.md` Section 3 | 🟡 Written |
| Database schema (PostgreSQL + PostGIS + InfluxDB) | `STRATEGY.md` Section 4 | 🟡 Written |
| Redis caching strategy | `STRATEGY.md` Section 4.2 | 🟡 Written |
| External interface port architecture (G1→G2, G2→G3) | `STRATEGY.md` Section 2.4 | 🟡 Written |
| Event flow diagrams | `STRATEGY.md` Section 3.2 | 🟡 Written |
| Technology decision log with rationale | `STRATEGY.md` Section 10 | 🟡 Written |

> Most of this is already written in STRATEGY.md. The report just needs to format it properly.

#### Deliverable 3: Development Details (G2 Owns This)

| What to document | Who Writes It | Status |
|-----------------|--------------|--------|
| Ingestion Service — MQTT bridge, validation pipeline, DLQ routing | **Janidu** | ⬜ Write after implementation |
| Stream Processing — Flink job design, GPS cleaning, anomaly L1 rules | **Natasha** | ⬜ Write after implementation |
| API Gateway — 3-layer pattern, WebSocket, ETA heuristic stub | **Nidharshan** | ⬜ Write after implementation |
| Route Management — PostGIS CRUD, ORM models, GeoJSON serving | **Chamodh** | ⬜ Write after implementation |
| Infrastructure — Docker orchestration, shared schemas, simulator | **Kusal** | ⬜ Write after implementation |
| Pydantic data contracts (GPSMessage, BusStatusMessage) | **Kusal** (maintains) | ⬜ Document schemas |
| ETA heuristic algorithm (`distance / speed`) | **Nidharshan** | ⬜ Write math explanation |
| Anomaly L1 rule engine (3 rules) | **Natasha** | ⬜ Write rule definitions |

#### Deliverable 4: Testing Reports (G2's Section)

| Test Type | Who | What to Report |
|-----------|-----|---------------|
| **Unit tests** | Each member for their service | Test count, coverage %, test descriptions |
| **Integration tests** | **Kusal** | End-to-end pipeline test results |
| **Load tests** | **Kusal or Natasha** | Locust results — messages/sec throughput |
| **Data validation** | **Janidu** | DLQ statistics — how many messages rejected, by what reason |

#### Deliverable 6: Project Management Evidence

| Evidence | How to Collect |
|----------|---------------|
| Sprint boards | Screenshot GitHub Projects board at end of each sprint |
| Burndown charts | GitHub Projects or manually track story points |
| Standup notes | Keep a shared Google Doc with daily updates (even brief) |
| Sprint retrospectives | Document what went well / what to improve after each sprint |
| PR history | GitHub PR list shows code review evidence |
| Commit history | `git log --oneline` shows contribution distribution |

#### Deliverable 10: Individual Reports (Each G2 Member)

Each person writes **2 pages** covering:
1. What they built (their service)
2. Technical challenges faced and how they solved them
3. What they learned
4. Their contribution to the team

---

## 3. G2 Member → Report Section Mapping

| G2 Member | Their Service | Report Sections They Write |
|-----------|-------------|---------------------------|
| **Janidu** | Ingestion Service | Ingestion architecture, MQTT bridge design, validation pipeline, DLQ design, unit test results |
| **Natasha** | Stream Processing | Flink job design, GPS cleaning algorithm, L1 anomaly rules, InfluxDB write strategy |
| **Nidharshan** | API Gateway | 3-layer pattern, WebSocket design, ETA heuristic math, REST API documentation |
| **Chamodh** | Route Management | PostGIS schema design, ORM model documentation, GeoJSON serving, route CRUD design |
| **Kusal** | Infrastructure | Docker architecture, shared schema documentation, simulator design, integration test results |

---

## 4. Important Notes & Warnings

### Things That Can Catch You Off Guard

> **Evidence is everything.** The evaluators don't just want working code — they want PROOF of process. Screenshots, commit history, PR reviews, meeting notes. Start collecting evidence NOW, not at the end.

> **Individual reports are mandatory.** Each of the 20 students must submit 2 pages. Don't leave this to the last week. Start a draft after you finish your service.

> **Live demo is critical.** The demo must show the complete system working end-to-end across all 4 groups. This means cross-group integration testing MUST happen before the demo. Plan at least 1 week for integration.

> **The report is a GROUP report.** All 4 subgroups contribute sections to ONE unified document. Coordinate the structure early so sections don't contradict each other.

### What G2 Does NOT Need to Do

| Not G2's Problem | Whose Problem |
|-----------------|---------------|
| Prometheus server setup & dashboards | **G4** (we just expose `/metrics`) |
| Kong API Gateway configuration | **G4** |
| Keycloak / OAuth2 / JWT setup | **G4** (we validate tokens they give us) |
| Kubernetes deployment manifests | **G4** (we give them Dockerfiles) |
| Mobile app UI / React Native | **G3** |
| Map rendering (Mapbox) | **G3** |
| User training materials & help docs | **G3** |
| Blockchain / Smart Contracts | **G4** |
| Device hardware design / circuit | **G1** |
| MQTT broker selection on edge | **G1** (we run Mosquitto for dev, they run production edge broker) |

### What G2 MUST Do (Non-Negotiable for Report)

| Must Have | Why |
|-----------|-----|
| Working Kafka pipeline (simulator → ingestion → Flink → Redis → WebSocket) | Core demo requirement |
| At least 70% unit test coverage | Evaluation criteria |
| Swagger API docs (auto-generated by FastAPI) | Deliverable 8: user training/API docs |
| Docker Compose that works with `docker compose up` | Deliverable 5: deployment |
| Sprint evidence (boards, PRs, commits) | Deliverable 6: project management |
| Architecture diagrams (already in STRATEGY.md) | Deliverable 2: design spec |
| 5 individual reports (2 pages each) | Deliverable 10 |

### Cross-Group Integration Timeline

| When | What | Groups |
|------|------|--------|
| Sprint 2 (mid) | G1 sends test MQTT messages → G2 ingestion validates | G1 + G2 |
| Sprint 3 (start) | G2 WebSocket feed → G3 renders bus on map | G2 + G3 |
| Sprint 3 (mid) | G4 deploys G2 services to staging K8s | G2 + G4 |
| Sprint 3 (end) | Full end-to-end demo rehearsal | All |
| Demo day | Live demo: GPS device → MQTT → Kafka → Flink → Map | All |

### Documentation That Already Exists (Don't Rewrite)

These files in your repo can be reformatted directly into report sections:

| File | Maps to Report Section |
|------|----------------------|
| `STRATEGY.md` | Deliverable 2 (Design Specification) — architecture, tech decisions |
| `PROJECT_PLAN.md` | Deliverable 7 (Work Estimation) — increment breakdown, sprint mapping |
| `docs/srs/SRS_G2_*.md` | Deliverable 1 (SRS) — already done |
| `docs/PROJECT_INFO.md` | Deliverable 6 (Project Management) — group structure |
| `schemas/*.py` | Deliverable 3 (Dev Details) — data contracts |

---

*Last updated: 26th April 2026*
