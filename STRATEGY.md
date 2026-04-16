# OnTime G2 — Architecture & Technology Strategy

> **Version:** 1.1  
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
- Buses operate on a **fixed timetable** — no bus conflicts
- **Scheduling & dispatch are manual** — no scheduling service
- System starts at the moment **driver taps "Start Trip"**
- **Only Passenger and Driver** roles are active (no Scheduler UI)

---

## 1. Strategic Vision

G2's mission is to be the **intelligence backbone** of the OnTime Public Transport System. Every data-driven decision — from a passenger checking when their bus arrives to a driver managing their trip — flows through G2's processing pipelines.

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

| Service | Port | Kafka Consumes | Kafka Produces | Increment |
|---------|------|----------------|----------------|-----------|
| **API Gateway** | 8000 | `eta.predictions`, `alerts.anomaly` | — | 0 (skeleton) |
| **Ingestion Service** | 8001 | — | `gps.raw`, `gps.dlq` | 1 |
| **Stream Processing** | — (Flink) | `gps.raw` | `gps.cleaned`, `gps.features` | 1 |
| **ETA Prediction** | 8002 | `gps.features` | `eta.predictions` | 2 (future) |
| **Anomaly Detection** | 8003 | `gps.features` | `alerts.anomaly` | 4 (future) |
| **Route Management** | 8004 | — | — | 1 |
| **Scheduling Service** | 8005 | `bus.status` | `schedule.dispatch` | 3 (future) |

### 2.3 Service Boundaries

Each service follows the **Single Responsibility Principle**:

- **Ingestion**: Validates GPS, bridges MQTT → Kafka. Knows nothing about ETA or anomalies.
- **Stream Processing**: Cleans GPS, extracts features. Pure data transformation — no business logic.
- **ETA Prediction** *(future)*: Loads ML model, runs inference, returns predictions.
- **Anomaly Detection** *(future)*: Runs 3-layer detection. Owns anomaly state and lifecycle.
- **Route Management**: CRUD for routes, stops, geofences. Serves route geometry.
- **Scheduling** *(future)*: Manages bus availability, departure slots, dispatch assignments.
- **API Gateway**: Aggregates data, serves WebSocket feed, manages caching.

---

## 3. Event-Driven Architecture

### 3.1 Kafka Topic Design

```
# Active in first release
gps.raw.{bus_id}          ← Raw GPS from MQTT bridge / simulator (1 Hz per bus)
gps.dlq                   ← Dead letter queue for invalid GPS messages
bus.status                ← Driver state changes (IDLE, DEPARTED, EN_ROUTE, etc.)

# Added in Increment 1+
gps.cleaned.{bus_id}      ← Kalman-filtered, map-matched GPS
gps.features.{bus_id}     ← 16-feature ML vectors per GPS point

# Future increments
eta.predictions           ← Per-bus ETA prediction updates
alerts.anomaly            ← Detected anomaly events
schedule.dispatch         ← Scheduler dispatch assignments
```

### 3.2 Event Flow

```
G1 GPS Device / GPS Simulator
    │ MQTT / direct Kafka (1 Hz)
    ▼
Ingestion Service
    │ Kafka: gps.raw
    ▼
Stream Processing (Flink — Inc 1)
    ├── Kalman filter → map match → gps.cleaned
    └── Feature extraction → gps.features (Inc 2)
         │
         ├──▶ ETA Prediction Service (Inc 2) → API Gateway → G3
         └──▶ Anomaly Detection Service (Inc 4) → API Gateway → G3
```

### 3.3 Message Guarantees

| Topic Pattern | Delivery | Partitioning | Retention |
|--------------|----------|--------------|-----------|
| `gps.*` | At-least-once | By `bus_id` | 7 days |
| `bus.*` | At-least-once | By `bus_id` | 30 days |
| `eta.*` | At-most-once | By `bus_id` | 1 day |
| `alerts.*` | At-least-once | By `bus_id` | 30 days |

---

## 4. Data Architecture

### 4.1 Database Strategy

**PostgreSQL 16 + PostGIS 3.4** is the primary data store. Services share a single PostgreSQL instance for the MVP (schema isolation for logical separation).

```
Schema: ingestion
  └── gps_readings (partitioned by date)

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

> **All schemas are created in Increment 0** via migration scripts, even for future services. This ensures the database structure is ready and documented upfront.

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

Both configured in a single `.env.example` — member uncomments the `DATABASE_URL` they need.

---

## 5. ML Strategy (Increment 2+)

> This section describes the ML approach planned for **Increment 2 onwards**. No ML models are trained or deployed in the first release.

### 5.1 Model Architecture

| Model | Algorithm | Purpose | Increment |
|-------|-----------|---------|-----------|
| **ETA (Urban)** | XGBoost Regressor | Predict arrival on urban roads | 2 |
| **ETA (Highway)** | XGBoost Regressor | Predict arrival on expressway | 2 |
| **ETA (Fallback)** | Physics Heuristic | `distance / speed` when ML unavailable | 2 |
| **Anomaly L1** | Z-Score | Detect speed/dwell outliers | 4 |
| **Anomaly L2** | Isolation Forest | Multi-dimensional anomaly detection | 4 |
| **Anomaly L3** | Rule Engine | Hard safety/operational rules | 4 |

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

The `/ws/live-feed` endpoint pushes a **complete fleet snapshot** every 1 second. This is a broadcast model — all connected clients receive the same payload.

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
  - zookeeper      # Kafka dependency
  - kafka           # Message broker
  - postgres        # PostgreSQL + PostGIS
  - redis           # Cache
  # Services added in Increment 1:
  # - ingestion
  # - flink-jobmanager
  # - flink-taskmanager
  # - api-gateway
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
| Database | PostgreSQL + PostGIS | Spatial queries, mature, free | MongoDB (no spatial), InfluxDB (no relational) |
| Cache | Redis | Sub-ms latency, pub/sub capability | Memcached (no pub/sub) |
| Message Broker | Apache Kafka | Event sourcing, replay, partitioning | RabbitMQ (no replay), Redis Streams (less durable) |
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

*Last updated: 16-th April 2026*
