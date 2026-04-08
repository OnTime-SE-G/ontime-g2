# OnTime G2 — Architecture & Technology Strategy

> **Version:** 1.0  
> **Date:** April 2026  
> **Author:** G2 — Data & Intelligence Team  
> **Status:** Approved

---

## 1. Strategic Vision

G2's mission is to be the **intelligence backbone** of the OnTime Public Transport System. Every data-driven decision — from a passenger checking when their bus arrives to an AI agent suggesting a schedule change — flows through G2's processing pipelines.

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Event-First** | All state changes flow as events through Kafka. No service directly mutates another's database. |
| **Contract-Driven** | Inter-service and inter-group interfaces are defined by schemas (Pydantic, JSON Schema) before code is written. |
| **Incremental Value** | Each increment delivers working software to real users. No "big bang" integration. |
| **Observable by Default** | Every service exposes health, metrics, and structured logs from Day 1. |
| **Fail Graceful** | ML model unavailable? Fall back to physics heuristic. Kafka down? Buffer locally. GPS lost? Interpolate. |

---

## 2. Microservices Architecture

### 2.1 Service Decomposition

G2 is decomposed into **7 independently deployable services**, each owning its own data and exposing well-defined APIs.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          G2 — Data & Intelligence                     │
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │  Ingestion   │  │   Stream     │  │    ETA       │                 │
│  │  Service     │──▶  Processing  │──▶  Prediction  │                 │
│  │              │  │  (Flink)     │  │  Service     │                 │
│  └──────────────┘  └──────┬───────┘  └──────┬───────┘                 │
│                           │                  │                         │
│  ┌──────────────┐  ┌──────▼───────┐  ┌──────▼───────┐                 │
│  │   Route      │  │  Anomaly     │  │  Scheduling  │                 │
│  │  Management  │  │  Detection   │  │  Service     │                 │
│  │  Service     │  │  Service     │  │              │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                        │
│  ┌────────────────────────────────────────────────────────────────┐    │
│  │                    API Gateway (FastAPI)                        │    │
│  │         REST + WebSocket + Prometheus Metrics                  │    │
│  └────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Service Catalog

| Service | Port | Database | Kafka Topics (Consume) | Kafka Topics (Produce) |
|---------|------|----------|----------------------|----------------------|
| **Ingestion Service** | 8001 | — | — | `gps.raw`, `gps.dlq` |
| **Stream Processing** | — (Flink job) | — | `gps.raw` | `gps.cleaned`, `gps.features` |
| **ETA Prediction** | 8002 | PostgreSQL (read-only) | `gps.features` | `eta.predictions` |
| **Anomaly Detection** | 8003 | PostgreSQL (read/write) | `gps.features` | `alerts.anomaly` |
| **Route Management** | 8004 | PostgreSQL (read/write) | — | — |
| **Scheduling Service** | 8005 | PostgreSQL (read/write) | `bus.status` | `schedule.dispatch` |
| **API Gateway** | 8000 | Redis (cache) | `eta.predictions`, `alerts.anomaly` | — |

### 2.3 Service Boundaries & Ownership

Each service follows the **Single Responsibility Principle**:

- **Ingestion**: Validates, bridges MQTT → Kafka. Knows nothing about ETA or anomalies.
- **Stream Processing**: Cleans GPS, extracts features. Pure data transformation — no business logic.
- **ETA Prediction**: Loads model, runs inference, returns predictions. Owns its model artifacts.
- **Anomaly Detection**: Runs 3-layer detection. Owns anomaly state and resolution lifecycle.
- **Route Management**: CRUD for routes, stops, geofences. Serves route geometry.
- **Scheduling**: Manages bus availability, departure slots, dispatch assignments. Owns schedule state.
- **API Gateway**: Aggregates data from all services, serves WebSocket feed, manages caching.

---

## 3. Event-Driven Architecture

### 3.1 Kafka Topic Design

```
gps.raw.{bus_id}          ← Raw GPS from MQTT bridge (1 Hz per bus)
gps.dlq                   ← Dead letter queue for invalid GPS messages
gps.cleaned.{bus_id}      ← Kalman-filtered, map-matched GPS
gps.features.{bus_id}     ← 16-feature ML vectors per GPS point
eta.predictions           ← Per-bus ETA prediction updates
alerts.anomaly            ← Detected anomaly events
bus.status                ← Driver state changes (IDLE, DEPARTED, etc.)
schedule.dispatch         ← Scheduler dispatch assignments
```

### 3.2 Event Flow

```
G1 GPS Device
    │ MQTT (1 Hz)
    ▼
Ingestion Service
    │ Kafka: gps.raw
    ▼
Stream Processing (Flink)
    ├── Kalman filter → map match → gps.cleaned
    └── Feature extraction → gps.features
         │
         ├──▶ ETA Prediction Service → eta.predictions → API Gateway → G3
         │
         └──▶ Anomaly Detection Service → alerts.anomaly → API Gateway → G3
```

### 3.3 Message Guarantees

| Topic Pattern | Delivery | Partitioning | Retention |
|--------------|----------|--------------|-----------|
| `gps.*` | At-least-once | By `bus_id` | 7 days |
| `eta.*` | At-most-once | By `bus_id` | 1 day |
| `alerts.*` | At-least-once | By `bus_id` | 30 days |
| `bus.*` | At-least-once | By `bus_id` | 30 days |
| `schedule.*` | At-least-once | By `route_id` | 30 days |

---

## 4. Data Architecture

### 4.1 Database Strategy

**PostgreSQL 16 + PostGIS 3.4** is the primary data store. Each service logically owns specific tables, but they share a single PostgreSQL instance for the MVP (physical separation in production via schema isolation).

```
Schema: ingestion
  └── gps_readings (partitioned by date)

Schema: routes
  ├── routes (LINESTRING geometry)
  ├── stops (POINT geometry)
  └── geofences (POLYGON geometry)

Schema: eta
  ├── trips
  └── stop_arrivals

Schema: anomaly
  └── anomalies

Schema: scheduling
  ├── buses
  ├── departure_slots
  ├── dispatch_assignments
  └── bus_availability
```

### 4.2 Caching Strategy (Redis)

| Key Pattern | TTL | Purpose |
|-------------|-----|---------|
| `bus:{bus_id}:position` | 5s | Latest GPS position for live feed |
| `bus:{bus_id}:eta` | 10s | Latest ETA prediction |
| `route:{route_id}:geojson` | 1h | Cached route geometry |
| `fleet:status` | 2s | Aggregated fleet status for WebSocket |

### 4.3 Time-Series Considerations

For future scaling, GPS time-series data may be migrated to **InfluxDB** or **TimescaleDB**. The current PostgreSQL partitioning strategy (by date) handles the MVP load comfortably.

---

## 5. ML Strategy

### 5.1 Model Architecture

| Model | Algorithm | Purpose | Training Data | Refresh Cycle |
|-------|-----------|---------|--------------|---------------|
| **ETA (Urban)** | XGBoost Regressor | Predict arrival time on urban segments | Historical trips (urban roads) | Weekly batch retrain |
| **ETA (Highway)** | XGBoost Regressor | Predict arrival time on expressway | Historical trips (highway) | Weekly batch retrain |
| **ETA (Fallback)** | Physics Heuristic | `distance / speed` when ML unavailable | — (no training) | — |
| **Anomaly L1** | Z-Score (Statistical) | Detect speed/dwell outliers | Rolling 5-min window | Real-time |
| **Anomaly L2** | Isolation Forest | Detect multi-dimensional anomalies | Normal trip data | Monthly retrain |
| **Anomaly L3** | Rule Engine | Hard safety/operational rules | — (configured) | On rule change |

### 5.2 Model Lifecycle (MLflow)

```
1. Data Collection → PostgreSQL (gps_readings, trips, stop_arrivals)
2. Feature Engineering → scripts/extract_features.py
3. Training → scripts/train_models.py → MLflow experiment tracking
4. Evaluation → scripts/evaluate_models.py → metrics logged to MLflow
5. Deployment → Model artifact → ETA Prediction Service loads at startup
6. Monitoring → Prediction confidence tracked via Prometheus metrics
7. Retraining → Triggered manually (MVP) → Airflow DAG (future)
```

### 5.3 Cold Start Strategy

When no trained model exists (first deployment):
1. **Physics heuristic** is the only active predictor
2. API responses include `model_version: "heuristic"` to signal fallback
3. GPS data is collected and stored for future training
4. After sufficient data (~1 week of operation), first model training is triggered

---

## 6. Security Strategy

### 6.1 Authentication & Authorization

| Layer | Mechanism | Owner |
|-------|-----------|-------|
| **Passenger App** | No auth required for public data (routes, ETAs) | G3 |
| **Driver App** | Bus-level credentials (static username/PIN) → Keycloak JWT | G4 (Keycloak) |
| **Scheduler Dashboard** | Username/password → Keycloak JWT | G4 (Keycloak) |
| **G1 → G2 (Machine-to-Machine)** | MQTT credentials + API key | G4 |
| **G3 → G2 (Server-to-Server)** | `X-API-Key` header | G2 validates |
| **G2 Internal Services** | Docker network isolation | G4 |

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

### 7.3 API Versioning Policy

- **Minor changes** (new optional fields): No version bump
- **Breaking changes** (removed/renamed fields): New version (`/v2/`)
- **Deprecation**: Old version supported for 2 sprints after new version launches

---

## 8. Observability Strategy

### 8.1 Three Pillars

| Pillar | Tool | Implementation |
|--------|------|----------------|
| **Metrics** | Prometheus | `/metrics` endpoint on each service; custom metrics for GPS throughput, ETA latency, anomaly counts |
| **Logs** | ELK Stack | Structured JSON logs via Python `structlog`; shipped to Elasticsearch by G4 |
| **Traces** | Jaeger | OpenTelemetry instrumentation on API Gateway + Flink jobs |

### 8.2 Key Metrics

```
# GPS Pipeline
gps_messages_received_total{bus_id}
gps_messages_rejected_total{reason}
gps_processing_latency_seconds

# ETA
eta_predictions_total{model_variant}
eta_prediction_latency_seconds
eta_model_confidence{bus_id}

# Anomaly
anomalies_detected_total{type, severity}
anomalies_resolved_total{type}

# API
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
| **Staging** | Pre-production validation | Kubernetes (G4 managed) |
| **Production** | Live system | Kubernetes (G4 managed) |

### 9.2 Docker Compose (Local Dev)

```yaml
services:
  - zookeeper      # Kafka dependency
  - kafka           # Message broker
  - postgres        # PostgreSQL + PostGIS
  - redis           # Cache
  - ingestion       # G2 Ingestion Service
  - flink-jobmanager # Flink cluster
  - flink-taskmanager
  - eta-service     # G2 ETA Service
  - anomaly-service # G2 Anomaly Service
  - api-gateway     # G2 API Gateway
```

### 9.3 CI/CD Pipeline (GitHub Actions)

```
Push to main → Lint + Type Check → Unit Tests → Build Docker Images
                                                       │
                                                       ▼
                                              Integration Tests
                                                       │
                                                       ▼
                                              Push to Container Registry
                                                       │
                                                       ▼
                                              Deploy to Staging (ArgoCD)
```

---

## 10. Technology Decision Log

| Decision | Choice | Rationale | Alternatives Considered |
|----------|--------|-----------|----------------------|
| ML Framework for ETA | XGBoost | Tabular data, fast inference, interpretable | LSTM (overkill for structured features), LightGBM (similar) |
| Stream Processing | Apache Flink (PyFlink) | True stream processing, watermarks, exactly-once | Spark Streaming (micro-batch), plain Kafka Streams |
| API Framework | FastAPI | Async, type-safe, auto-docs, Python native | Flask (no async), Django (too heavy) |
| Database | PostgreSQL + PostGIS | Spatial queries, mature, free | MongoDB (no spatial), InfluxDB (no relational) |
| Cache | Redis | Sub-ms latency, pub/sub capability | Memcached (no pub/sub) |
| Message Broker | Apache Kafka | Event sourcing, replay, partitioning | RabbitMQ (no replay), Redis Streams (less durable) |
| Anomaly Detection | 3-Layer hybrid | Statistical + ML + Rules covers all edge cases | Single ML model (no hard rules), pure rules (no learning) |
| Auth Provider | Keycloak (G4) | Centralized, RBAC, OIDC compliant | Custom auth (reinvent wheel), Firebase (vendor lock) |

---

## 11. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| G1 GPS data not arriving | No tracking possible | GPS simulator as fallback; mock data pipeline |
| ML model accuracy low | Bad ETA predictions | Physics heuristic fallback; confidence scores in API |
| Kafka broker failure | Pipeline stops | Multi-broker cluster; local buffering in ingestion |
| PostgreSQL overload | Slow queries | Read replicas; Redis caching; table partitioning |
| Cross-group integration delays | Feature blocked | Contract-first design; mock services for each interface |
| Sri Lankan network instability | GPS gaps | Interpolation for <30s gaps; degraded mode for >60s |

---

*Last updated: April 2026*
