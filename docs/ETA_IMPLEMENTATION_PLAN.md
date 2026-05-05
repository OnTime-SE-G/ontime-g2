# ETA Implementation Plan — Inc 1 (Math Model) + Inc 2 (XGBoost ML)

**Authors:** Kusal (Lead), Nidarshan (Member)  
**Status:** Awaiting Team Approval

---

## Background

As discussed by JPabasara, ETA delivery is split into two increments:

1. **Inc 1 — Mathematical model** with defined API contracts so other groups can integrate and test immediately.
2. **Inc 2 — XGBoost ML model** trained on synthetic data (no real historical data is available within the time constraint). Physics model remains as a sanity fallback.

---

## Target Architecture

```
G1 GPS Device
  → MQTT → Ingestion Service → transport-telemetry-raw (Kafka)
                                         ↓
                              Flink EnrichmentFunction
                         (adds nextStopId, distanceToNextStop, stopsRemaining)
                                         ↓
                             gps-cleaned (NEW Kafka topic)
                                         ↓
                      ETA Service (Kafka consumer, background task)
                      Inc 1 → distance / max(speed, 1.4 m/s)
                      Inc 2 → XGBoost predict(features)
                                         ↓
                        Redis Pub/Sub channel: eta:live
                                         ↓
                     WebSocket Service → Frontend / Other groups

HTTP on-demand:
  GET /api/v1/eta/{busId}/{stopId}?model=physics|xgboost
  → API Gateway → ETA Service → response
```

**Key design decision:** `gps-cleaned` is a **new** Kafka topic and does **not** replace `transport-telemetry-cleaned` — the anomaly service and existing consumers are left unchanged.

---

## Pre-requisite — P-0 (Kusal, must land first)

Extend `services/route-service/app/routers/internal.py`:

- **New endpoint:** `GET /internal/routes/{routeId}/stops`
- **Response:**
  ```json
  [
    { "id": 1, "name": "Kadawatha Junction", "stop_order": 1, "lat": 7.003, "lon": 80.121 },
    { "id": 2, "name": "Gampaha", "stop_order": 2, "lat": 7.085, "lon": 80.012 }
  ]
  ```
- Ordered by `stop_order` ascending.
- Used by Flink at startup to cache stop sequences per route.

---

## Phase 1 — Increment 1: Mathematical ETA

### Kusal's Tasks

| ID | File | Description |
|----|------|-------------|
| K-1 | `services/route-service/app/routers/internal.py` | Add `GET /internal/routes/{routeId}/stops` endpoint (P-0) |
| K-2 | `services/stream-processing/app/utils/route_client.py` | Add `fetch_stops_sync(route_id)` — httpx call to `/internal/routes/{routeId}/stops`; cache result in-memory per `routeId` at startup |
| K-3 | `services/stream-processing/app/transforms/enrichment.py` | In `process_element()`: after computing `routeProgressPct`, determine the next unvisited stop and add `nextStopId` (int), `distanceToNextStop` (float, metres), `stopsRemaining` (int) to the enriched message |
| K-4 | `services/stream-processing/app/job.py` + `app/config.py` | Add second `KafkaSink` writing the enriched stream to a new `gps-cleaned` topic; add `KAFKA_GPS_CLEANED_TOPIC` env var (default: `gps-cleaned`) |
| K-5 | `services/eta-service/models/eta.py` | Update `compute_eta(distance_m, speed_ms)` — formula: `distance_m / max(speed_ms, 1.4)`; `model_used = "physics"` |
| K-6 | `services/stream-processing/tests/` | Unit tests for stop-distance calculation: mock route geometry + stop list, assert `nextStopId`, `distanceToNextStop`, `stopsRemaining` in output |

### Nidarshan's Tasks

| ID | File | Description |
|----|------|-------------|
| N-1 | `services/eta-service/consumer.py` (NEW) | Kafka consumer for `gps-cleaned`; on each message calls `compute_eta(distanceToNextStop, speed)`; publishes result to Redis `eta:live` |
| N-2 | `services/eta-service/main.py` | Start Kafka consumer as asyncio background task via FastAPI `lifespan` |
| N-3 | `services/eta-service/routers/eta.py` | Add `GET /eta/{busId}/{stopId}?model=physics` on-demand endpoint; reads bus position from Redis `bus:{busId}:position`; fetches stop coords from route-service |
| N-4 | `services/eta-service/requirements.txt` | Add `kafka-python` |
| N-5 | `services/eta-service/tests/unit/` | Tests: physics edge cases (zero speed, zero distance, min-speed clamp), Kafka consumer mock, HTTP endpoint mock (≥10 tests) |

### Redis `eta:live` message shape (agreed contract)

```json
{
  "event": "eta_update",
  "busId": "BUS-001",
  "stopId": 42,
  "stopName": "Kadawatha Junction",
  "eta_seconds": 120.5,
  "model_used": "physics",
  "routeProgressPct": 65.3,
  "distanceToNextStop": 234.5,
  "timestamp": "2026-05-05T01:00:00Z"
}
```

---

## Phase 2 — Increment 2: XGBoost ML Model

### Kusal's Tasks

| ID | File | Description |
|----|------|-------------|
| K-7 | `services/eta-service/models/training/generate_data.py` (NEW) | Generate ~5000 synthetic samples; features: `[distance_m, speed_ms, hour_of_day, day_of_week, is_weekend, stops_remaining]`; traffic multipliers: rush hours 7–9am & 5–7pm = ×1.25; weekends midday = ×1.15 |
| K-8 | `services/eta-service/models/training/train_xgb.py` (NEW) | Train `XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05)`, 80/20 split, print RMSE + MAE, save artifact as `eta_model_xgb.joblib` |
| K-9 | `services/eta-service/models/ml_eta_xgb.py` (NEW) | `predict_eta_xgb(distance_m, speed_ms, stops_remaining) → EtaResult`; features include `hour_of_day`, `day_of_week`, `is_weekend`; physics sanity clamp ±80%; `model_used = "xgboost"` |
| K-10 | `services/eta-service/tests/unit/test_ml_eta_xgb.py` | Test: artifact loads, rush-hour ETA > off-peak ETA, zero distance → 0 seconds, clamping activates when prediction diverges |

### Nidarshan's Tasks

| ID | File | Description |
|----|------|-------------|
| N-6 | `services/eta-service/consumer.py` | Wire XGBoost into consumer; use `stops_remaining` from `gps-cleaned` message as feature; default model = XGBoost in Inc 2; fallback to physics on any error |
| N-7 | `services/eta-service/routers/eta.py` | `?model=xgboost\|physics` param; add clear docstring with example request/response for other groups to copy |
| N-8 | `services/eta-service/tests/` | End-to-end: mock `gps-cleaned` Kafka message → verify XGBoost ETA appears on `eta:live` Redis channel |

---

## API Contracts (published after Inc 1 — other groups integrate against these)

### HTTP — On-demand ETA

```
GET /api/v1/eta/{busId}/{stopId}?model=physics

Response 200:
{
  "busId":       "BUS-001",
  "stopId":      42,
  "eta_seconds": 120.5,
  "distance_m":  234.5,
  "speed_ms":    1.95,
  "model_used":  "physics",
  "clamped":     false,
  "timestamp":   "2026-05-05T01:00:00Z"
}

Response 503: { "detail": "No real-time position for bus BUS-001" }
Response 404: { "detail": "Stop 42 not found" }
```

### WebSocket — Live ETA push

Connect to the existing endpoint (no change needed for other groups):
```
WS /v1/live?routeId=1
```

ETA update messages will arrive automatically:
```json
{
  "event":             "eta_update",
  "busId":             "BUS-001",
  "stopId":            42,
  "stopName":          "Kadawatha Junction",
  "eta_seconds":       120.5,
  "model_used":        "physics",
  "routeProgressPct":  65.3,
  "distanceToNextStop": 234.5,
  "timestamp":         "2026-05-05T01:00:00Z"
}
```

---

## Files Changed / Created (Summary)

| File | Owner | Change |
|------|-------|--------|
| `services/route-service/app/routers/internal.py` | Kusal | Add `/internal/routes/{routeId}/stops` |
| `services/stream-processing/app/utils/route_client.py` | Kusal | Add `fetch_stops_sync()` |
| `services/stream-processing/app/transforms/enrichment.py` | Kusal | Add stop-distance enrichment fields |
| `services/stream-processing/app/job.py` | Kusal | Add `gps-cleaned` Kafka sink |
| `services/stream-processing/app/config.py` | Kusal | Add `KAFKA_GPS_CLEANED_TOPIC` env var |
| `services/stream-processing/tests/` | Kusal | Flink enrichment unit tests |
| `services/eta-service/models/eta.py` | Kusal | Update physics formula |
| `services/eta-service/models/training/generate_data.py` | Kusal | NEW — synthetic data |
| `services/eta-service/models/training/train_xgb.py` | Kusal | NEW — XGBoost training |
| `services/eta-service/models/ml_eta_xgb.py` | Kusal | NEW — XGBoost predictor |
| `services/eta-service/tests/unit/test_ml_eta_xgb.py` | Kusal | XGBoost model tests |
| `services/eta-service/consumer.py` | Nidarshan | NEW — Kafka consumer + Redis publisher |
| `services/eta-service/main.py` | Nidarshan | Add consumer background task |
| `services/eta-service/routers/eta.py` | Nidarshan | Add `GET /eta/{busId}/{stopId}` |
| `services/eta-service/requirements.txt` | Nidarshan | Add `kafka-python` |
| `services/eta-service/tests/unit/` | Nidarshan | Consumer + HTTP endpoint tests |

---

## Verification Checklist

**Inc 1:**
- [ ] `pytest services/stream-processing/tests/` — all pass
- [ ] `pytest services/eta-service/tests/` — ≥20 tests pass
- [ ] GPS simulator → `gps-cleaned` topic messages contain `nextStopId`, `distanceToNextStop`, `stopsRemaining`
- [ ] `GET /api/v1/eta/BUS-001/1` → returns valid `eta_seconds`
- [ ] WebSocket `/v1/live?routeId=1` → `eta_update` events visible live

**Inc 2:**
- [ ] `python3 train_xgb.py` → RMSE < 60 s, `eta_model_xgb.joblib` saved
- [ ] `GET /api/v1/eta/BUS-001/1?model=xgboost` → `"model_used": "xgboost"`
- [ ] Rush-hour ETA > off-peak ETA (sanity check)

---

## Scope Boundaries

- `transport-telemetry-cleaned` and all its consumers (anomaly service) are **not touched**
- WebSocket service requires **no code changes** — it already subscribes to `eta:live`
- Existing GBR model (PR #66) is **archived** in Inc 2 and replaced by XGBoost
- XGBoost training uses **synthetic data only** — no real historical data available within the time constraint
