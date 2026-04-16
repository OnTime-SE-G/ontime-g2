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

**OnTime** is a real-time public transport intelligence platform for Sri Lanka. It tracks live bus positions, predicts arrival times using ML models, and provides passengers and drivers with the information they need — when they need it.

The system is built as a **distributed microservices architecture** processing 1 Hz GPS streams through Apache Kafka, running ML-based ETA predictions, and exposing data through REST APIs and WebSocket feeds.

### The Problem

Commuters at intermediate bus halts across Sri Lanka have **zero reliable information** about approaching buses. They over-wait, miss buses, or make uninformed decisions daily. Drivers operate without pacing feedback or trip lifecycle management.

### The Solution

OnTime's first release focuses on two core user roles:

| Role | Platform | Core Value |
|------|----------|------------|
| **Passenger** | Mobile (Flutter) | Live map with bus positions, ETA on tap, route search |
| **Bus Driver** | Mobile (Flutter) | Trip state management (Start/End trip), target times, issue reporting |

> **Note:** Scheduler/Dispatcher functionality is planned for a future release. For the first release, buses operate on a fixed timetable and scheduling is handled manually.

---

## 🏗️ System Architecture

```
┌─────────────┐     MQTT      ┌──────────────┐    Kafka     ┌──────────────────┐
│  G1 — Edge  │──────────────▶│  G2 — Data   │────────────▶│  G2 — Stream     │
│  (GPS/IoT)  │               │  Ingestion    │             │  Processing      │
└─────────────┘               └──────────────┘             └────────┬─────────┘
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

| Category | Technology | When Used |
|----------|-----------|-----------|
| **Language** | Python 3.12 | All increments |
| **API Framework** | FastAPI | Inc 0+ |
| **Message Broker** | Apache Kafka (Confluent 7.6) | Inc 0+ |
| **Database** | PostgreSQL 16 + PostGIS 3.4 | Inc 0+ |
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
│
├── docs/
│   ├── PROJECT_INFO.md          # Group structure & deliverables
│   └── srs/
│       ├── SRS_G2_Data_Intelligence_1.0.docx   # Original SRS
│       └── SRS_G2_Data_Intelligence_1.1.md      # Updated SRS v1.1
│
├── services/                    # Microservices
│   ├── ingestion/               # GPS ingestion service
│   ├── api-gateway/             # FastAPI gateway
│   ├── stream-processing/       # Flink pipeline (Inc 1+)
│   ├── eta-service/             # ETA prediction API (Inc 2+)
│   ├── anomaly-service/         # Anomaly detection (Inc 4+)
│   └── route-service/           # Route management
│
├── models/                      # ML model artifacts (Inc 2+)
├── scripts/                     # Seeding, simulators, training
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

# 2. Copy environment config
cp .env.example .env
# Edit .env — uncomment the DATABASE_URL you want (local or Neon cloud)

# 3. Start infrastructure (Kafka, PostgreSQL, Redis)
docker compose -f docker/docker-compose.yml up -d

# 4. Install Python dependencies
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows
pip install -r requirements.txt

# 5. Seed route & stop data
python scripts/seed_routes.py

# 6. Start the API server
uvicorn app.main:app --reload --port 8000

# 7. (Optional) Start GPS simulator
python scripts/gps_simulator.py
```

### Verify Installation

```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

---

## 📊 API Endpoints (First Release)

| Method | Endpoint | Description | Increment |
|--------|----------|-------------|-----------|
| `GET` | `/health` | Service health check | 0 |
| `GET` | `/metrics` | Prometheus metrics | 0 |
| `GET` | `/api/v1/routes` | List all routes with stops | 1 |
| `GET` | `/api/v1/routes/{route_id}/buses` | Active buses on a route | 1 |
| `WS` | `/ws/live-feed` | Real-time fleet status stream (1s) | 1 |
| `POST` | `/api/v1/bus/{bus_id}/status` | Driver changes bus state | 1 |
| `POST` | `/api/v1/ingest/gps` | GPS test ingestion endpoint | 1 |

<details>
<summary><strong>Future Endpoints (Inc 2+)</strong></summary>

| Method | Endpoint | Description | Increment |
|--------|----------|-------------|-----------|
| `GET` | `/api/v1/eta/{bus_id}` | ETA for all downstream stops | 2 |
| `GET` | `/api/v1/eta/{bus_id}/{stop_id}` | ETA for a specific stop | 2 |
| `GET` | `/api/v1/anomalies/active` | All unresolved anomalies | 4 |
| `POST` | `/api/v1/bus/{bus_id}/issue` | Driver reports issue | 4 |
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
