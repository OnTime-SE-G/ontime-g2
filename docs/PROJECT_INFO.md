# Group G — Public Transport System: Project Information

> **Project Title:** Real-Time Public Transport Tracking & ETA Prediction System  
> **Module:** SE3080 / SE3070 Software Engineering  
> **University:** University of Moratuwa  
> **Date:** April 2026  
> **Status:** Active Development

---

## 1. Project Overview

Group G is building a **real-time public transport intelligence platform** for Sri Lanka. The system tracks live bus positions via GPS, predicts arrival times using ML models, enables smart dispatching, and provides role-specific interfaces for passengers, drivers, and schedulers.

### System Domain

| Aspect | Detail |
|--------|--------|
| **Domain** | Public Transportation |
| **Geography** | Sri Lanka (MVP: Moratuwa → Kadawatha route) |
| **End Users** | Passengers, Bus Drivers, Schedulers/Dispatchers |
| **Data Sources** | GPS devices (G1), IR sensors (future), manual input |
| **Key Output** | Live tracking, ETA predictions, anomaly alerts, scheduling |

---

## 2. Main Group Structure

Group G consists of **4 subgroups**, each with **5 students**. Each subgroup has a specific technical focus area but must collaborate across boundaries.

```
Group G (20 students total)
├── G1 — Device & Edge Systems
├── G2 — Data & Intelligence         ◀ This repository
├── G3 — System Engineering & Interaction
└── G4 — Platform, Security & Integration
```

---

## 3. Subgroup Responsibilities & Tools

### G1 — Device & Edge Systems

| Aspect | Details |
|--------|---------|
| **Focus** | IoT / Embedded boundary |
| **Responsibilities** | GPS tracking, data transmission, filter noisy GPS signals, detect route deviations, sensor integration (multi-device), edge processing and filtering, offline data buffering, device lifecycle management |
| **Key Functions** | GPS tracking, data transmission, filter noisy GPS signals, detect route deviations |
| **Recommended Tools** | ESP32, GPS modules, MQTT, Mosquitto/EMQX, Node-RED, ThingsBoard, Eclipse Leshan, Wireshark |

### G2 — Data & Intelligence (This Subgroup)

| Aspect | Details |
|--------|---------|
| **Focus** | Data Engineering + AI |
| **Responsibilities** | Data ingestion & storage, stream + batch processing, AI/ML model development, ETA prediction & analytics, delay detection, data validation and quality checks |
| **Key Functions** | ETA prediction, delay detection, build ETA + anomaly models, stream processing of location data |
| **Recommended Tools** | Python, Apache Kafka, Apache Flink, PostgreSQL, PyTorch/TensorFlow, FastAPI, InfluxDB, Apache Spark, MLflow, Airflow, Great Expectations |

### G3 — System Engineering & Interaction

| Aspect | Details |
|--------|---------|
| **Focus** | System logic, UX, and system core |
| **Responsibilities** | Foundational/core logic & integration points, web & mobile apps, dashboards & visualization, real-time user interactions, role-based UIs, UI/UX design & responsiveness |
| **Key Functions** | Live tracking map, delay notifications, role-specific interfaces |
| **Recommended Tools** | Next.js, Flutter, Redux/Zustand, Socket.IO, Mapbox, Three.js, Storybook |

### G4 — Platform, Security & Integration

| Aspect | Details |
|--------|---------|
| **Focus** | DevOps + system-wide concerns |
| **Responsibilities** | CI/CD pipelines & automation, API gateway & service routing, authentication & authorization, system monitoring & observability, infrastructure provisioning, blockchain/smart contracts |
| **Key Functions** | Service deployment, API management, gateway, monitoring |
| **Recommended Tools** | Docker, Kubernetes, Helm, Terraform, Kong, Istio, GitHub Actions, Argo CD, Prometheus, Grafana, ELK Stack, Jaeger, Keycloak, HashiCorp Vault, OPA, Trivy, OWASP ZAP |

---

## 4. Required Technical Demonstrations

All subgroups must demonstrate competency in the following areas:

### System Complexity
- [x] Microservices architecture
- [ ] Event-driven communication (Kafka / Flink)
- [ ] Sync + async processing

### Real-Time + Batch Processing
- [ ] Streaming pipelines
- [ ] Batch analytics pipelines
- [ ] Hybrid architectures

### Security Engineering
- [ ] OAuth2 / OpenID Connect (Keycloak)
- [ ] Role-based access control
- [ ] Secrets management (Vault)
- [ ] API security + penetration testing
- [ ] Blockchain, Hyperledger, and Smart Contracts

### Observability & Monitoring
- [ ] Metrics (Prometheus)
- [ ] Dashboards (Grafana)
- [ ] Logs (ELK Stack)
- [ ] Tracing (Jaeger)

### DevOps & Platform Engineering
- [ ] Containerization (Docker)
- [ ] Orchestration (Kubernetes)
- [ ] GitOps (Argo CD)
- [ ] Infrastructure as Code (Terraform)
- [ ] CI/CD pipelines (GitHub Actions)

### Quality & Reliability
- [ ] Unit + Integration + System testing
- [ ] Chaos testing (failure simulation)
- [ ] Load testing
- [ ] Data validation

---

## 5. Inter-Group Interfaces

### G1 → G2 Interface (Input)

| Property | Value |
|----------|-------|
| **Protocol** | MQTT over TCP (port 1883) |
| **MQTT Topics** | `gps/bus/{bus_id}` — position data |
| | `gps/bus/{bus_id}/status` — bus status events |
| **Frequency** | 1 Hz per active bus |
| **Payload Format** | JSON (see SRS v1.1 Section 7.1) |
| **Bridge** | G2's `mqtt_bridge.py` converts MQTT → Kafka topics |

### G2 → G3 Interface (Output)

| Property | Value |
|----------|-------|
| **REST Base URL** | `http://g2-api:8000` (internal Docker network) |
| **WebSocket** | `ws://g2-api:8000/ws/live-feed` |
| **Format** | JSON, UTF-8 |
| **Auth** | `X-API-Key` header for server-to-server |
| **Push Rate** | 1-second intervals for live feed |

### G2 ↔ G4 Interface (Platform)

| Property | Value |
|----------|-------|
| **Deployment** | Docker images built by G4 CI/CD |
| **Health** | `GET /health` — dependency status |
| **Metrics** | `GET /metrics` — Prometheus format |
| **Auth** | Keycloak JWT validation for user-facing endpoints |
| **Config** | All via environment variables (`.env`) |

---

## 6. Deliverables Checklist

The main group must submit a project report containing the following:

| # | Deliverable | Status | Owner |
|---|------------|--------|-------|
| 1 | Complete SRS (Functional, NFR, Domain, RE process) | 🟡 In Progress | G2 lead |
| 2 | Complete Design Specification (Architecture at large + specific) | ⬜ Not Started | All |
| 3 | Development details, algorithms, data models | ⬜ Not Started | G2 |
| 4 | Testing reports (Unit, System, UAT) | ⬜ Not Started | All |
| 5 | Deployment plan, config, security & perf testing | ⬜ Not Started | G4 |
| 6 | Project Management (Agile Scrum with evidence) | ⬜ Not Started | All |
| 7 | Work estimation & deliverable plans (with evidence) | ⬜ Not Started | All |
| 8 | User training & operational support | ⬜ Not Started | G3 |
| 9 | Software evolution plan (CR process with evidence) | ⬜ Not Started | All |
| 10 | Individual work reports (2 pages × 20 students) | ⬜ Not Started | Individual |

### Communication & Demo

- Project presentation of work done
- Live demo of the complete system
- Cross-subgroup integration demonstration

---

## 7. Agile Process

The team follows **Agile Scrum** methodology:

| Ceremony | Frequency | Notes |
|----------|-----------|-------|
| Sprint Planning | Start of each 2-week sprint | All subgroups |
| Daily Standup | Daily (15 min) | Within subgroup |
| Sprint Review | End of sprint | Demo to all groups |
| Sprint Retrospective | End of sprint | Process improvement |
| Backlog Refinement | Mid-sprint | Product Owner + leads |

### Tools

| Tool | Purpose |
|------|---------|
| GitHub Projects | Sprint boards, issue tracking |
| GitHub Actions | CI/CD pipelines |
| Discord / Slack | Team communication |
| Google Docs | Meeting minutes, shared documents |

---

## 8. Evaluation Criteria

Projects are evaluated on:

1. **Project Report** — Completeness, technical depth, clarity
2. **Project Communication** — Presentation quality, Q&A handling
3. **Demo** — Working system, real-time functionality, integration quality
4. **Individual Contribution** — Per-student work reports (2 pages each)

---

*Last updated: April 2026*
