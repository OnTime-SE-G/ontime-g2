# OnTime G2 — Architecture & Technology Strategy

> **Version:** 2.0  
> **Date:** April 2026  
> **Author:** G2 — Data & Intelligence Team  
> **Status:** Approved

---

## 0. First Release Scope

> **Read this first.** The strategy below describes the full product vision. For the first release, only a subset is active.

| What's Active (Inc 0–1) | What's Deferred (Inc 2+) |
|-------------------------|--------------------------|
| Docker infra (Kafka, PG, Redis) | Apache Flink stream processing |
| PostgreSQL + PostGIS schemas | ETA prediction (XGBoost) |
| GPS ingestion (simulator → Kafka) | Anomaly detection (3-layer) |
| FastAPI skeleton (`/health`, `/metrics`) | Scheduling & dispatch service |
| Bus state machine (driver taps) | MLflow, model training |
| WebSocket live feed | Route search, GTFS import |

**Key assumptions for first release:**
- Buses operate on a **fixed timetable** - no bus conflicts
- **Scheduling & dispatch are manual** - no scheduling service
- System starts at the moment **driver taps "Start Trip"**
- **Only Passenger and Driver** roles are active (no Scheduler UI)

---

## 1. Strategic Vision

G2's mission is to be the **intelligence backbone** of the OnTime Public Transport System. Every data-driven decision, from a passenger checking when their bus arrives to a driver managing their trip, flows through G2's processing pipelines.

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Event-First** | All state changes flow as events through Kafka. No service directly mutates another's database. |
| **Contract-Driven** | Inter-service and inter-group interfaces are defined by schemas (Pydantic, JSON Schema) before code is written. |
| **Incremental Value** | Each increment delivers working software. No "big bang" integration. |
| **Observable by Default** | Every service exposes health, metrics, and structured logs from Day 1. |
| **Fail Graceful** | ML model unavailable? Fall back to physics heuristic. Kafka down? Buffer locally. GPS lost? Interpolate. |

---

## 2. Microservices Architecture

### 2.1 Service Decomposition

G2 is decomposed into independently deployable services. Services marked **(future)** are not built in the first release.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          G2 — Data & Intelligence                     │
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │  Ingestion   │  │   Stream     │  │    ETA       │                 │
│  │  Service     │──▶  Processing  │──▶  Prediction  │                 │
│  │   (Inc 1)    │  │  (Inc 1)     │  │  (Inc 2)     │                 │
│  └──────────────┘  └──────┬───────┘  └──────┬───────┘                 │
│                           │                  │                         │
│  ┌──────────────┐  ┌──────▼───────┐  ┌──────▼───────┐                 │
│  │   Route      │  │  Anomaly     │  │  Scheduling  │                 │
│  │  Management  │  │  Detection   │  │  Service     │                 │
│  │   (Inc 1)    │  │  (Inc 4)     │  │  (Inc 3)     │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    API Gateway (FastAPI)  — Inc 0              │    │
│  │         REST + WebSocket + Prometheus Metrics                  │    │
│  └────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Catalog

| Service | Port | AutoMQ Consumes | AutoMQ Produces | Increment |
|---------|------|----------------|----------------|-----------|
| **API Gateway** | 8000 | `transport-anomaly-alerts` | — | 0 (skeleton) |
| **Ingestion Service** | 8001 | — | `transport-telemetry-raw`, `transport-telemetry-dlq` | 1 |
| **Stream Processing** | — (Flink) | `transport-telemetry-raw` | — | 1 |
| **ETA Prediction** | 8002 | `transport-telemetry-raw` | `eta.predictions` | 2 (future) |
| **Anomaly Detection** | 8003 | `transport-telemetry-raw` | `transport-anomaly-alerts` | 4 (future) |
| **Route Management** | 8004 | — | — | 1 |
| **Scheduling Service** | 8005 | `bus.status` | `schedule.dispatch` | 3 (future) |

### 2.3 Service Boundaries

Each service follows the **Single Responsibility Principle**:

- **Ingestion**: Validates GPS, bridges MQTT → Kafka. Knows nothing about ETA or anomalies.
- **Stream Processing**: Cleans GPS, extracts features. Pure data transformation, no business logic.
- **ETA Prediction** *(future)*: Loads ML model, runs inference, returns predictions.
- **Anomaly Detection** *(future)*: Runs 3-layer detection. Owns anomaly state and lifecycle.
- **Route Management**: CRUD for routes, stops, geofences. Serves route geometry.
- **Scheduling** *(future)*: Manages bus availability, departure slots, dispatch assignments.
- **API Gateway**: Aggregates data, serves WebSocket feed. Internally enforces a strict 3-Layer Pattern (`routers/` for HTTP, `services/` for business logic, and `models/` for data/math) ensuring the true streaming pipeline seamlessly connects to mathematical stubs without frontend awareness.

### 2.5 Bus State Machine (SRS v2.0 FR-G3.2)

```
WAITING_AT_DEPOT → DEPARTED_ORIGIN → EN_ROUTE → ARRIVED_DESTINATION
                                         ↕
                                  INCIDENT_REPORTED
ARRIVED_DESTINATION → WAITING_AT_DEPOT  (Admin reset)
```

> **Note:** The `IDLE` state from v1.1 is removed. `INCIDENT_REPORTED` is a new state triggered by driver incident reports.

### 2.6 Incident Reporting (SRS v2.0 FR-G3.3)

Drivers report structured incidents via `POST /api/v1/trips/{id}/incident`:

| Incident Code | Description |
|---------------|-------------|
| `BREAKDOWN` | Vehicle mechanical failure |
| `ACCIDENT` | Traffic accident |
| `HEAVY_TRAFFIC` | Severe traffic congestion |
| `ROAD_CLOSURE` | Road is blocked/closed |
| `MEDICAL_EMERGENCY` | Passenger medical emergency |

Reporting an incident transitions the bus to `INCIDENT_REPORTED` state and fires an admin alert. Mapped to **Increment 4**.

### 2.7 Driver Delay Reporting (SRS v2.0 FR-G2.5)

Drivers submit delay reports via `POST /api/v1/driver/report-delay`:

| Field | Type | Values |
|-------|------|--------|
| `reason` | enum | `TRAFFIC`, `BREAKDOWN`, `ACCIDENT`, `OTHER` |
| `estimatedMinutes` | int | Estimated delay duration |

Backend applies an additive offset to all downstream ETAs for that bus. Mapped to **Increment 2**.

## 2.4 External Interface Port Architecture

G2 communicates through separate logical ports for independent data flows.

### Inputs from G1 → G2

| Port | Content | Fields |
|------|---------|--------|
| Port 1 — GPS Location | Constant positional data | busId, routeId, lat, lng, speed, satellites, deviation, timestamp |
| Port 2 — Occupancy Buffer | Crowd density data | busId, crowdStatus (NOT_FULL / SEMI_FULL / FULL), timestamp |

### Outputs from G2

| Output Port | Content | Fields |
|------------|---------|--------|
| Output 1 — Live Position Feed | Real-time bus positions | busId, routeId, lat, lng, speed, timestamp |
| Output 2 — Crowd & ETA Feed | Occupancy + predictions | busId, crowdStatus, etaSeconds, confidence, timestamp |

---

## 3. Event-Driven Architecture

### 3.1 AutoMQ Topic Design

> **Note:** AutoMQ brokers are **stateless**. This means topic partitions are stored directly in cloud object storage (like AWS S3) rather than on physical broker disks, guaranteeing rapid 10-second scaling without the "partition tax" of traditional standard Kafka.

```
# Active in first release
transport-telemetry-raw  ← Raw telemetry from MQTT bridge / simulator (every 3–5 seconds per bus)
transport-telemetry-dlq  ← Dead letter queue for invalid telemetry messages
bus.status                ← Driver state changes (WAITING_AT_DEPOT, DEPARTED_ORIGIN, EN_ROUTE, ARRIVED_DESTINATION, INCIDENT_REPORTED)

# Future increments
eta.predictions           ← Per-bus ETA prediction updates
transport-anomaly-alerts  ← Detected anomaly events
schedule.dispatch         ← Scheduler dispatch assignments
```

### 3.2 Event Flow

```
G1 GPS Device / GPS Simulator
    │ MQTT / direct Kafka (3–5 second publish interval)
    ▼
Ingestion Service
    │ Kafka: transport-telemetry-raw
    ▼
Stream Processing (Flink — Inc 1)
         │
         ├──▶ ETA Prediction Service (Inc 2) → API Gateway → G3
         └──▶ Anomaly Detection Service (Inc 4) → transport-anomaly-alerts → API Gateway → G3
```

### 3.3 Message Guarantees

| Topic Pattern | Delivery | Partitioning | Retention |
|--------------|----------|--------------|-----------|
| `transport-telemetry-*` | At-least-once | By `busId` | 7 days |
| `bus.status` | At-least-once | By `busId` | 30 days |
| `eta.predictions` | At-most-once | By `busId` | 1 day |
| `transport-anomaly-alerts` | At-least-once | By `busId` | 30 days |

---

## 4. Data Architecture

### 4.1 Database Strategy

The primary data store is split into two specialized databases to maximize performance and elasticity:

**1. PostgreSQL 16 + PostGIS 3.4 (Static/Relational)**
Used for core business logic, users, and geographic routes. Services share a single PostgreSQL instance for the MVP (schema isolation).

```
Schema: routes
  ├── routes (LINESTRING geometry)
  ├── stops (POINT geometry)
  └── geofences (POLYGON geometry)

Schema: fleet
  ├── buses (status, assigned route)
  ├── trips (journey records)
  └── stop_arrivals (actual vs scheduled)

Schema: anomaly                    ← Inc 4 (future)
  └── anomalies

Schema: scheduling                 ← Inc 3 (future)
  ├── departure_slots
  ├── dispatch_assignments
  └── bus_availability
```

**2. InfluxDB (Time-Series / Telemetry)**
Used strictly for high-throughput stream storage and historical aggregation.

```
Bucket: telemetry
  ├── gps_readings (bus_id, lat, lng, speed, heading, timestamp)
  └── eta_predictions (bus_id, stop_id, eta)
```

> **All schemas and buckets are created in Increment 0** via migration and init scripts, even for future services. This ensures the database structure is ready and documented upfront.

### 4.2 Caching Strategy (Redis)

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `bus:{bus_id}:position` | 5s | Latest GPS position for live feed |
| `bus:{bus_id}:status` | 30s | Current bus state |
| `route:{route_id}:geojson` | 1h | Cached route geometry |
| `fleet:status` | 2s | Aggregated fleet status for WebSocket |

### 4.3 Database Access: Local + Cloud

| Environment | Database | Usage |
|-------------|---------|-------|
| **Local Dev** | Docker PostgreSQL + PostGIS | Solo coding, fast iteration, CI pipeline |
| **Cloud (Neon)** | Neon PostgreSQL | Shared team DB, real data collaboration |

Both configured in a single `.env.example` - member uncomments the `DATABASE_URL` they need.

---

## 5. ML Strategy (Increment 2+)

> This section describes the ML approach planned for **Increment 2 onwards**. No ML models are trained or deployed in the first release.

### 5.1 Model Architecture

| Model | Algorithm | Purpose | Increment |
|-------|-----------|---------|-----------|
| **ETA (Urban)** | XGBoost Regressor | Predict arrival on urban roads | 2 |
| **ETA (Highway)** | XGBoost Regressor | Predict arrival on expressway | 2 |
| **ETA (Fallback)** | Physics Heuristic | `distance / speed` when ML unavailable | 2 |
| **Anomaly L1** | Rule Engine | Deterministic rules (FR-G2.3 baseline) | 1 |
| **Anomaly L2** | Z-Score | Statistical outlier detection on speed/dwell-time per segment | 2 |
| **Anomaly L3** | Isolation Forest | Multi-dimensional anomaly detection | 3/4 |

### 5.2 Anomaly Detection — Incremental Delivery

The 3-layer anomaly pipeline is delivered incrementally:

| Layer | Approach | Increment | Scope |
|-------|----------|-----------|-------|
| **Layer 1 — Rule Engine** | Deterministic rules (FR-G2.3 baseline) | Inc 1 | 3 rules: Stationary bus (speed < 2 km/h for > 5 min), Off-route deviation (Haversine > 50m from polyline), Communication loss (no telemetry > 3 min during active trip) |
| **Layer 2 — Statistical** | Z-Score on speed/dwell-time per segment | Inc 2 | Statistical outlier detection on per-segment metrics |
| **Layer 3 — ML** | Isolation Forest on multivariate features | Inc 3/4 | Full multi-dimensional anomaly detection |

### 5.3 Crowd State Thresholds (SRS v2.0)

| State | Occupancy Range |
|-------|-----------------|
| `NOT_FULL` | 0–40% |
| `SEMI_FULL` | 41–75% |
| `FULL` | 76–100% |

### 5.2 Cold Start Strategy

When no trained model exists (Increments 0–1):
1. **Physics heuristic** is the only active predictor
2. API responses include `model_version: "heuristic"`
3. GPS data is collected and stored for future training
4. First model training triggered manually after sufficient data (~1 week of operation)

---

## 6. Security Strategy

### 6.1 Authentication & Authorization

| Layer | Mechanism | Owner |
|-------|-----------|-------|
| **Passenger App** | No auth for public data (routes, ETAs) | G3 |
| **Driver App** | Bus-level credentials → Keycloak JWT | G4 (Keycloak) |
| **G1 → G2 (M2M)** | MQTT credentials + API key | G4 |
| **G3 → G2 (S2S)** | `X-API-Key` header | G2 validates |
| **G2 Internal** | Docker network isolation | G4 |

### 6.2 Security Controls

- **No hardcoded secrets**: All credentials via environment variables
- **Parameterized queries**: ORM (SQLAlchemy) prevents SQL injection
- **Rate limiting**: Public REST endpoints: 60 req/min/IP
- **CORS**: Restricted to G3 frontend origins
- **Input validation**: Pydantic models on all API inputs
- **GPS bounding box**: Reject coordinates outside Sri Lanka (lat 5.9–9.9, lng 79.5–81.9)

---

## 7. API Design Strategy

### 7.1 REST API Conventions

```
Base URL: /api/v1/
Content-Type: application/json
Versioning: URL prefix (/v1/, /v2/)
Error format: {"detail": "message", "error_code": "CODE"}
Pagination: ?limit=N&offset=M (default limit=20, max=100)
```

### 7.2 WebSocket Strategy

The `wss://api.ontime.lk/v1/live` endpoint pushes delta updates whenever telemetry events are processed (~every 3–5 seconds per active bus). On first connect, the server pushes the full current fleet state, then deltas only. **Crucially, the WebSocket router is strictly forbidden from manually looping fake coordinates. It must solely subscribe to Redis Pub/Sub channels populated by the upstream Flink pipeline to guarantee a true end-to-end data flow.**

**Why broadcast, not per-bus subscriptions?**
- Fleet size is small (≤50 buses for MVP)
- Simpler client implementation for G3
- Single Redis key to read vs. N pub/sub channels
- Per-bus filtering done client-side

---

## 8. Observability Strategy (Increment 1+)

> Basic health/metrics endpoints are set up in Increment 0. Full observability (traces, dashboards) comes later.

| Pillar | Tool | Status |
|--------|------|--------|
| **Metrics** | Prometheus (`/metrics` endpoint) | Inc 0 (basic) |
| **Logs** | Structured JSON via `structlog` | Inc 1+ |
| **Traces** | Jaeger / OpenTelemetry | Future |

### Key Metrics (planned)

```
gps_messages_received_total{bus_id}
gps_messages_rejected_total{reason}
api_request_duration_seconds{method, endpoint, status}
websocket_connected_clients
```

---

## 9. Deployment Strategy

### 9.1 Environments

| Environment | Purpose | Infra |
|-------------|---------|-------|
| **Local Dev** | Individual development | Docker Compose |
| **Integration** | Cross-service testing | Docker Compose (shared) |
| **Staging** | Pre-production | Kubernetes (G4 managed — future) |
| **Production** | Live system | Kubernetes (G4 managed — future) |

### 9.2 Docker Compose (Local Dev — Increment 0)

```yaml
services:
  - broker          # Confluent Local Kafka (KRaft mode, no Zookeeper needed)
  - postgres        # PostgreSQL + PostGIS + pgAdmin
  - redis           # Cache & Pub/Sub
  - influxdb        # Time-series telemetry
  # Services built out natively in Increment 1:
  # - api-gateway
  # - flink-jobmanager
```

### 9.3 CI/CD Pipeline (GitHub Actions)

```
Push to any branch → Lint (ruff) → Type Check (mypy) → Unit Tests (pytest) → Build Docker
```

> Full deployment pipeline (ArgoCD, container registry) is set up by G4 in later sprints.

---

## 10. Technology Decision Log

| Decision | Choice | Rationale | Alternatives Considered |
|----------|--------|-----------|----------------------|
| ML Framework for ETA | XGBoost | Tabular data, fast inference, interpretable | LSTM (overkill), LightGBM (similar) |
| Stream Processing | Apache Flink (PyFlink) | True stream processing, watermarks, exactly-once | Spark Streaming (micro-batch), Kafka Streams |
| API Framework | FastAPI | Async, type-safe, auto-docs, Python native | Flask (no async), Django (too heavy) |
| Database | PostgreSQL + PostGIS | Spatial queries, mature, free | MongoDB (no spatial) |
| Telemetry Database | InfluxDB | Time-series optimized, handles massive write throughput from streams | PostgreSQL Partitioning (overhead, scale issues) |
| Cache | Redis | Sub-ms latency, pub/sub capability | Memcached (no pub/sub) |
| Message Broker | AutoMQ (Cloud) / Confluent Local (Dev) | AutoMQ provides S3-backed elastic scaling for cloud. Confluent Local provides effortless 1-node KRaft for local dev. Both share exact same Kafka API. | Apache Kafka (Disk-bound), RabbitMQ |
| Anomaly Detection | 3-Layer hybrid | Statistical + ML + Rules covers all edge cases | Single ML model, pure rules |
| Auth Provider | Keycloak (G4) | Centralized, RBAC, OIDC compliant | Custom auth, Firebase (vendor lock) |

---

## 11. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| G1 GPS data not arriving | No tracking possible | GPS simulator as fallback for all G2 testing |
| ML model accuracy low | Bad ETA predictions | Physics heuristic fallback; confidence scores in API |
| Kafka broker failure | Pipeline stops | Multi-broker cluster; local buffering in ingestion |
| PostgreSQL overload | Slow queries | Read replicas; Redis caching; table partitioning |
| Cross-group integration delays | Feature blocked | Contract-first design; mock services for each interface |

---

*Last updated: 19th April 2026*
