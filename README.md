<p align="center">
  <img src="docs/assets/logo-placeholder.png" alt="OnTime Logo" width="120" />
</p>

<h1 align="center">OnTime — Public Transport Real-Time Tracking & ETA Prediction</h1>

<p align="center">
  <strong>Group G — SE3080 / SE3070 Software Engineering Project</strong><br/>
  University of Moratuwa · April 2026
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-active-brightgreen" alt="Status" />
  <img src="https://img.shields.io/badge/version-0.1.0--dev-blue" alt="Version" />
  <img src="https://img.shields.io/badge/architecture-microservices-purple" alt="Architecture" />
  <img src="https://img.shields.io/badge/license-academic-orange" alt="License" />
</p>

---

## 📖 Overview

**OnTime** is a real-time public transport intelligence platform for Sri Lanka. It tracks live bus positions, predicts arrival times using ML models, enables smart scheduling, and provides passengers, drivers, and dispatchers with the information they need — when they need it.

The system is built as a **distributed microservices architecture** processing 1 Hz GPS streams through Apache Kafka and Flink, running ML-based ETA predictions, and exposing data through REST APIs and WebSocket feeds.

### The Problem

Commuters at intermediate bus halts across Sri Lanka have **zero reliable information** about approaching buses. They over-wait, miss buses, or make uninformed decisions daily. Drivers operate without pacing feedback, and dispatchers rely on manual rotation queues with no real-time fleet visibility.

### The Solution

OnTime provides three role-specific experiences:

| Role | Platform | Core Value |
|------|----------|------------|
| **Passenger** | Mobile (Flutter) | Live map with bus positions, ETA on tap, route search |
| **Bus Driver** | Mobile (Flutter) | Trip state management, target times, issue reporting |
| **Scheduler** | Web (Next.js) | Fleet dashboard, departure slot dispatch, anomaly alerts |

---

## 🏗️ System Architecture

```
┌─────────────┐     MQTT      ┌──────────────┐    Kafka     ┌──────────────────┐
│  G1 — Edge  │──────────────▶│  G2 — Data   │────────────▶│  G2 — Stream     │
│  (GPS/IoT)  │               │  Ingestion    │             │  Processing      │
└─────────────┘               └──────────────┘             │  (Flink)         │
                                                            └────────┬─────────┘
                                                                     │
                    ┌────────────────────────────────────────────────┤
                    │                    │                            │
              ┌─────▼──────┐    ┌───────▼────────┐    ┌─────────────▼───────┐
              │ ETA Model  │    │ Anomaly Detect │    │  PostgreSQL/PostGIS │
              │ (XGBoost)  │    │ (3-Layer)      │    │  + Redis Cache      │
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
              │ (Flutter)  │   │ (Next.js)   │   │ (K8s/Docker) │
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

| Category | Technology |
|----------|-----------|
| **Language** | Python 3.12 |
| **API Framework** | FastAPI |
| **Stream Processing** | Apache Flink (PyFlink) |
| **Message Broker** | Apache Kafka (Confluent 7.6) |
| **Database** | PostgreSQL 16 + PostGIS 3.4 |
| **Cache** | Redis |
| **ML Framework** | XGBoost, scikit-learn (Isolation Forest) |
| **ML Ops** | MLflow |
| **Data Validation** | Pydantic v2, Great Expectations |
| **Containerization** | Docker |
| **Orchestration** | Kubernetes (managed by G4) |
| **Monitoring** | Prometheus metrics endpoint |
| **Testing** | pytest, locust (load testing) |

---

## 📁 Repository Structure

```
ontime-g2/
├── README.md                    # This file
├── PROJECT_PLAN.md              # Incremental delivery plan
├── STRATEGY.md                  # Architecture & technology strategy
│
├── docs/
│   ├── PROJECT_INFO.md          # Group structure & deliverables
│   ├── srs/
│   │   ├── SRS_G2_Data_Intelligence_1.0.docx   # Original SRS
│   │   └── SRS_G2_Data_Intelligence_1.1.md      # Updated SRS v1.1
│   └── assets/                  # Diagrams, images
│
├── services/                    # Microservices (future)
│   ├── ingestion/               # GPS ingestion service
│   ├── stream-processing/       # Flink pipeline
│   ├── eta-service/             # ETA prediction API
│   ├── anomaly-service/         # Anomaly detection
│   ├── route-service/           # Route management
│   ├── scheduling-service/      # Trip scheduling
│   └── api-gateway/             # FastAPI gateway
│
├── models/                      # ML model artifacts
├── scripts/                     # Training, data seeding, simulators
├── docker/                      # Docker & Compose files
└── tests/                       # Unit, integration, system tests
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

# 2. Start infrastructure (Kafka, PostgreSQL, Redis)
docker compose -f docker/docker-compose.yml up -d

# 3. Install Python dependencies
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 4. Seed route & stop data
python scripts/seed_routes.py

# 5. Start the API server
uvicorn app.main:app --reload --port 8000

# 6. (Optional) Start GPS simulator
python scripts/gps_simulator.py
```

### Verify Installation

```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

---

## 📊 Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `GET` | `/api/v1/eta/{bus_id}` | ETA for all downstream stops |
| `GET` | `/api/v1/eta/{bus_id}/{stop_id}` | ETA for a specific stop |
| `GET` | `/api/v1/anomalies/active` | All unresolved anomalies |
| `GET` | `/api/v1/routes` | List all routes with stops |
| `GET` | `/api/v1/routes/{route_id}/buses` | Active buses on a route |
| `WS` | `/ws/live-feed` | Real-time fleet status stream (1s) |
| `GET` | `/metrics` | Prometheus metrics |

Full API documentation available at `http://localhost:8000/docs` (Swagger UI).

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests (requires Docker infra)
pytest tests/integration/ -v

# Run load tests
locust -f tests/load/locustfile.py
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
