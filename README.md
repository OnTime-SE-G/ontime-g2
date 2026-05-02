<div align="center">
  <br/>
  <a href="https://github.com/OnTime-SE-G/ontime-g2">
    <img src="docs/assets/OnTime_logo_v_1.jpg" alt="OnTime Logo" width="180" style="border-radius: 20px;" />
  </a>
  <br/><br/>

  <h1>OnTime — Public Transport Real-Time Tracking & ETA Prediction</h1>

  <p>
    <strong>Group G — SE3080 / SE3070 Software Engineering Project</strong><br/>
    University of Moratuwa · April 2026
  </p>

  <p>
    <img src="https://img.shields.io/badge/status-active-brightgreen" alt="Status" />
    <img src="https://img.shields.io/badge/version-0.1.0--dev-blue" alt="Version" />
    <img src="https://img.shields.io/badge/architecture-microservices-purple" alt="Architecture" />
    <img src="https://img.shields.io/badge/license-academic-orange" alt="License" />
  </p>
</div>

---

## 📖 Overview

**OnTime** is a real-time public transport intelligence platform for Sri Lanka. It tracks live bus positions, predicts arrival times using ML models, and provides passengers and drivers with the information they need, when they need it.

The system is built as a **distributed microservices architecture** processing GPS streams (every 3–5 seconds per bus) through Apache Kafka, running ML-based ETA predictions, and exposing data through REST APIs and WebSocket feeds.

### The Problem

Commuters at intermediate bus halts across Sri Lanka have **zero reliable information** about approaching buses. They over-wait, miss buses, or make uninformed decisions daily. Drivers operate without pacing feedback or trip lifecycle management.

### The Solution

OnTime's first release focuses on two core user roles:

| Role | Platform | Core Value |
|------|----------|------------|
| **Passenger** | Mobile (React Native) | Live map with bus positions, ETA on tap, route search |
| **Bus Driver** | Mobile (React Native) | Trip state management (Start/End trip), target times, issue reporting |

> **Note:** Scheduler/Dispatcher functionality is planned for a future release. For the first release, buses operate on a fixed timetable and scheduling is handled manually.

---

## 🏗️ System Architecture

```
┌─────────────┐     MQTT      ┌──────────────┐   AutoMQ   ┌──────────────────┐
│  G1 — Edge  │──────────────▶│  G2 — Data   │────────────▶│  G2 — Stream     │
│  (GPS/IoT)  │               │  Ingestion    │             │  Processing      │
└─────────────┘               └──────────────┘             └────────┬─────────┘
                                                                     │
                    ┌────────────────────────────────────────────────┤
                    │                    │                            │
              ┌─────▼──────┐    ┌───────▼────────┐    ┌─────────────▼───────┐
              │ ETA Model  │    │ Anomaly Detect │    │  PostgreSQL/PostGIS │
              │ (XGBoost)  │    │ (3-Layer)      │    │  & InfluxDB + Redis │
              └─────┬──────┘    └───────┬────────┘    └─────────┬───────────┘
                    │                    │                        │
              ┌─────▼────────────────────▼────────────────────────▼───┐
              │             G2 API (FastAPI)                          │
              │   REST + WebSocket /live-feed                        │
              └───────────────────────┬──────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                   │
              ┌─────▼─────┐   ┌──────▼──────┐   ┌───────▼──────┐
              │ G3 Mobile  │   │ G3 Web      │   │ G4 Platform  │
              │(React      │   │ (React.js)  │   │ (K8s/Docker) │
              │ Native)    │   │             │   │              │
              └────────────┘   └─────────────┘   └──────────────┘
```

---

## 👥 Group Structure

**Group G** consists of four subgroups, each with 5 members:

| Subgroup | Focus Area | Key Responsibilities |
|----------|-----------|---------------------|
| **G1** — Device & Edge | IoT / Embedded | GPS tracking, data transmission, noise filtering, route deviation detection |
| **G2** — Data & Intelligence | Data Engineering + AI | ETA prediction, delay detection, stream processing, ML models |
| **G3** — System Eng & Interaction | System Logic, UX | Live tracking app, notifications, dashboards, maps |
| **G4** — Platform, Security & Integration | DevOps + Security | CI/CD, Kubernetes, API gateway, monitoring, auth |

> **This repository (`ontime-g2`)** contains **G2's** codebase, documentation, and ML models.

---

## 🛠️ Technology Stack (G2)

| Category | Technology | When Used |
|----------|-----------|-----------|
| **Language** | Python 3.12 | All increments |
| **API Framework** | FastAPI | Inc 0+ |
| **Message Broker** | AutoMQ (Kafka-compatible, S3-backed) | Inc 0+ |
| **Databases** | PostgreSQL 16 (Relational/Spatial) + InfluxDB (Time-Series) | Inc 0+ |
| **Cache** | Redis | Inc 0+ |
| **Stream Processing** | Apache Flink (PyFlink) | Inc 1+ |
| **ML Framework** | XGBoost, scikit-learn | Inc 2+ |
| **ML Ops** | MLflow | Inc 2+ |
| **Data Validation** | Pydantic v2 | All increments |
| **Containerization** | Docker | All increments |
| **Testing** | pytest, locust (load testing) | All increments |

---

## 📁 Repository Structure

```
ontime-g2/
├── README.md                    # This file
├── PROJECT_PLAN.md              # Incremental delivery plan
├── STRATEGY.md                  # Architecture & technology strategy
├── requirements.txt             # Root Python dependencies
├── pytest.ini                   # Test configuration & custom markers
│
├── schemas/                     # Shared Pydantic data contracts
│   ├── __init__.py              # Centralized re-exports
│   ├── gps.py                   # GPSMessage — canonical GPS telemetry schema
│   ├── bus_status.py            # BusLifecycleState, BusStatusMessage
│   └── geo_config.py            # CoordinateBounds, SRI_LANKA_BOUNDS
│
├── services/                    # Microservices (each is a deployable unit)
│   ├── api-gateway/             # FastAPI gateway (main.py, Dockerfile)
│   ├── ingestion/               # GPS ingestion service (Inc 1+)
│   ├── stream-processing/       # Flink pipeline (Inc 1+)
│   ├── eta-service/             # ETA prediction API (Inc 2+)
│   ├── anomaly-service/         # Anomaly detection (Inc 4+)
│   └── route-service/           # Route management
│
├── scripts/                     # CLI tools: seeding, simulation
│   ├── seed_routes.py           # KML parser + PostGIS seeder
│   ├── gps_simulator.py         # MQTT GPS telemetry publisher
│   └── models/                  # Script-specific: ORM models + config
│       ├── base.py              # SQLAlchemy DeclarativeBase
│       ├── db_route.py          # RouteORM, StopORM
│       ├── route.py             # RouteSeed, RouteGeometry, Stop
│       └── settings.py          # Environment configuration
│
├── models/                      # ML model artifacts (Inc 2+)
├── data/                        # Static data files (KML, GTFS)
├── docker/                      # Docker Compose + env config
├── docs/                        # Documentation & SRS
└── tests/                       # ALL tests (unit, integration, load)
    ├── unit/                    # Fast, isolated unit tests
    └── integration/             # Tests requiring Docker infra
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- Git

### Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ontime-g2.git
cd ontime-g2

# 2. Copy environment config
cp docker/.env.example docker/.env
# Edit .env — uncomment the connections you want (local Docker URLs or Cloud connections like Neon PG / InfluxDB Cloud)

# 3. Start infrastructure locally
# Note: Production uses AutoMQ (cloud-native Kafka), but local dev spins up standard Kafka/Zookeeper, PostgreSQL, InfluxDB, and Redis.
docker compose -f docker/docker-compose.yml up -d

# 4. Install Python dependencies
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 5. Seed route & stop data
python scripts/seed_routes.py

# 6. Start the API server
cd services/api-gateway && uvicorn main:app --reload --port 8000

# 7. Start the ingestion service
python -m services.ingestion.app.main

# 8. (Optional) Start GPS simulator
python scripts/gps_simulator.py
```

### Verify Installation

```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

### Ingestion Service 

The ingestion service is now wired into local Docker Compose as `ingestion-service`.

Quick start:

```bash
docker compose -f docker/docker-compose.yml up -d broker mqtt-broker ingestion-service
curl http://localhost:8001/health
curl http://localhost:8001/health/ready
```

Runtime package layout:

```text
services/ingestion/
  app/    # runtime code
  tests/  # service tests
```

Cross-group interfaces around ingestion:

- G1 connects to G2 ingestion over MQTT using topic `transport/bus/{busId}/location`.
- G1 payloads must match the shared `GPSMessage` contract in `schemas/gps.py`.
- G4 connects to ingestion over HTTP for operations and monitoring using `/health`, `/health/live`, `/health/ready`, and `/metrics`.
- G4 deploys or supervises the service through Docker Compose now and can later reuse the same readiness and metrics endpoints for Kubernetes and Prometheus.

---

## 📊 API Endpoints (First Release)

| Method | Endpoint | Description | Increment |
|--------|----------|-------------|-----------|
| `GET` | `/health` | Service health check | 0 |
| `GET` | `/metrics` | Prometheus metrics | 0 |
| `GET` | `/api/v1/buses/live` | Live bus positions for all active buses | 1 |
| `GET` | `/api/v1/routes` | List all routes with stops | 1 |
| `GET` | `/api/v1/routes/{route_id}/buses` | Active buses on a route | 1 |
| `WS` | `wss://api.ontime.lk/v1/live` | Real-time fleet status (delta updates, ~3–5s) | 1 |
| `POST` | `/api/v1/trips/{id}/state` | Driver changes trip/bus state | 1 |
| `POST` | `/api/v1/driver/start-trip` | Driver starts a trip | 1 |
| `POST` | `/api/v1/driver/report-delay` | Driver reports delay (reason + minutes) | 1 |
| `POST` | `/api/v1/ingest/gps` | GPS test ingestion endpoint | 1 |

<details>
<summary><strong>Future Endpoints (Inc 2+)</strong></summary>

| Method | Endpoint | Description | Increment |
|--------|----------|-------------|-----------|
| `GET` | `/api/v1/eta/{bus_id}/{stop_id}` | ETA for a specific stop | 2 |
| `POST` | `/api/v1/driver/report-delay` | ETA engine applies additive downstream offset from delay reports persisted in Increment 1 | 2 |
| `POST` | `/api/v1/trips/{id}/incident` | FR-G3.3 structured incident report (BREAKDOWN, ACCIDENT, HEAVY_TRAFFIC, ROAD_CLOSURE, MEDICAL_EMERGENCY) → sets `INCIDENT_REPORTED` + triggers admin alert | 4 |
| `GET` | `/api/v1/admin/fleet` | Admin fleet overview | 4 |
| `GET` | `/api/v1/admin/alerts` | Active anomaly alerts | 4 |
| `POST` | `/api/v1/admin/alerts/{id}/acknowledge` | Admin acknowledges alert | 4 |
| `POST` | `/api/v1/admin/dispatch` | Admin dispatch bus | 3 |
| `POST` | `/api/v1/admin/slots/{id}/assign` | Admin assigns bus to departure slot | 3 |
| `GET` | `/api/v1/routes/search` | Route search | 5 |
| `GET` | `/api/v1/routes/nearest` | Nearest routes by location | 5 |

</details>

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests (requires Docker infra)
pytest tests/integration/ -v

# Run load tests
locust -f tests/load/locustfile.py

# Run ingestion service tests
python -m pytest services/ingestion/tests -v
```

---

## 📄 Documentation

| Document | Description |
|----------|-------------|
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | Incremental delivery roadmap with sprint mapping |
| [STRATEGY.md](STRATEGY.md) | Architecture decisions and technology rationale |
| [SRS v1.1](docs/srs/SRS_G2_Data_Intelligence_1.1.md) | Full Software Requirements Specification |
| [PROJECT_INFO.md](docs/PROJECT_INFO.md) | Group structure, deliverables, and evaluation criteria |

---

## 📝 License

This project is developed as part of the SE3080/SE3070 Software Engineering module at the University of Moratuwa. All rights reserved by the respective contributors.

---

<p align="center">
  <strong>OnTime G2 — Data & Intelligence</strong><br/>
  Built with ☕ at University of Moratuwa
</p>
