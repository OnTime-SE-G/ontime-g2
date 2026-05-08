# Plan: Off-Route Detection · Persistent Anomaly · ETA Persistence · SARIMA Forecasting

**Authors:** Kusal (Lead)  
**Status:** Awaiting Approval (Chamodh, Janidu)  
**Relates to:** ETA pipeline (`ETA` branch, PR #92), Inc 2

---

## Problem Statement

The existing `gps-cleaned` Kafka topic feeds the ETA Service directly from the Flink
EnrichmentFunction. However:

1. **Flink already detects off-route positions** (via route geometry projection) but discards
   the deviation distance — it does not emit a flag the ETA Service can use.
2. **A single off-route fix may be GPS noise.** Only a sustained off-route streak (3+
   consecutive readings) indicates the bus genuinely deviated and ETA should be suppressed.
3. **All computed ETA values are currently ephemeral** (Redis TTL 300 s). There is no
   persistent record for retrospective analysis or future ML training.
4. **SARIMA time-series forecasting** is a natural next step once per-stop ETA history
   accumulates — it models the repeating hour-of-day / day-of-week seasonality that XGBoost
   cannot capture without careful feature engineering.

---

## Architecture Overview

```
Flink EnrichmentFunction
  ├── already computes projection min-distance internally
  └── NEW: expose it as offRoute (bool) + offRouteDistanceM (float) on every enriched message
        ↓
  transport-telemetry-cleaned  (existing consumers unaffected — additive field)
  gps-cleaned                  (ETA Service consumer)
        ↓
  ┌──────────────────────────────────────────────────┐
  │  Anomaly Service                                 │
  │  existing: single-hit OFF_ROUTE alert            │
  │  NEW:      off_route_streak counter per bus      │
  │            ≥ 3 consecutive → PERSISTENT_OFF_ROUTE│
  └──────────────────────────────────────────────────┘
        ↓
  ┌──────────────────────────────────────────────────┐
  │  ETA Service consumer                            │
  │  NEW guard: if offRoute → skip Redis + eta:live  │
  │  NEW persist: every valid ETA → eta_db           │
  └──────────────────────────────────────────────────┘
        ↓
  eta_db (PostgreSQL, separate logical DB)
        ↓
  train_sarima.py (offline CLI)
        ↓
  sarima_eta.py (GET /api/v1/eta/{tripId}/{stopId}?model=sarima)
```

---

## Database Isolation

| Database   | Service                        | Why separate                          |
|------------|--------------------------------|---------------------------------------|
| `ontime_db`| route-service, api-gateway     | Route/stop geometry, bus master data  |
| `fleet_db` | fleet-management-service       | Trip lifecycle, driver assignments    |
| `eta_db`   | **eta-service only** ← NEW     | ETA records, SARIMA training data     |

`eta_db` is a separate **logical database** on the same `ontime_postgres` container — identical
pattern already used by `fleet_db`. No PostGIS extension needed. Schema created by SQLAlchemy
`create_all()` at service startup; no root-level Alembic required.

---

## Phase 1 — `offRoute` field in Flink

### Files changed

| File | Change |
|------|--------|
| `services/stream-processing/app/utils/geo.py` | Add `distance_to_route(lat, lon, points) → float` |
| `services/stream-processing/app/transforms/enrichment.py` | Emit `offRoute` + `offRouteDistanceM` |
| `services/stream-processing/tests/unit/test_enrichment.py` | 2 new tests |

### `distance_to_route()`

Reuses the projection loop already inside `calculate_route_progress` — extracts and returns the
`min_dist` that is currently computed but thrown away. Zero overhead: the geometry is already
iterated on every message.

### Enriched message additions

```json
{
  "offRoute": true,
  "offRouteDistanceM": 83.4
}
```

- `offRoute: true` when projection distance > **50 m** (same threshold already used by the
  Anomaly Service `OFF_ROUTE` check — consistency).
- When `routeId` is `null` (bus not on a trip): `offRoute: false`, `offRouteDistanceM: 0.0`.
- **Both** `transport-telemetry-cleaned` and `gps-cleaned` carry these fields automatically
  because both sinks consume the same `processed_ds` — no extra sink code needed.

### Backward compatibility

Existing consumers of `transport-telemetry-cleaned` (Anomaly Service, InfluxDB sink) parse JSON
and ignore unknown fields — no breaking change.

---

## Phase 2 — Anomaly Service: `PERSISTENT_OFF_ROUTE` streak

### Files changed

| File | Change |
|------|--------|
| `services/anomaly-service/app/models/anomaly_model.py` | `off_route_streak_start_time` dict + time window logic |
| `services/anomaly-service/app/config.py` | `OFF_ROUTE_STREAK_WINDOW_SEC: int = 5` loaded as Env Var |
| `services/anomaly-service/tests/` | Streak unit tests |

### Logic

```
detect(telemetry, geometry):
  # use precomputed flag if Flink provides it; else compute locally (backward-compat)
  is_off = telemetry.get("offRoute") ?? (distance_to_polyline(...) > 50)
  current_time = telemetry.get("timestamp")

  if is_off:
    if bus_id not in streak_start:
      streak_start[bus_id] = current_time
      emit OFF_ROUTE alert         # existing single-hit alert (unchanged)
    
    elapsed = current_time - streak_start[bus_id]
    if elapsed >= OFF_ROUTE_STREAK_WINDOW_SEC:
      emit PERSISTENT_OFF_ROUTE alert
  else:
    streak_start.pop(bus_id, None) # reset on any on-route reading
```

**Why a 5-second time window?**  
A fixed time window is more robust than a strict count of pings (which assumes a perfect 1Hz frequency). 5 seconds of continuous off-route readings guarantees the bus genuinely deviated and avoids firing on fleeting GPS noise. Constant is stored in `app/config.py`.

### New alert type

```json
{
  "anomalyType": "PERSISTENT_OFF_ROUTE",
  "message": "Bus off-route for 3 consecutive readings (≥150 m deviation streak)",
  "busId": "BUS-007",
  "tripId": "TRIP-2026-001",
  "routeId": "1",
  "streakCount": 3
}
```

---

## Phase 3 — Infrastructure: `eta_db`

### Files changed

| File | Change |
|------|--------|
| `docker/init/01-databases.sql` | Add `CREATE DATABASE eta_db;` |
| `docker/docker-compose.yml` | Add `ETA_DATABASE_URL` env to `eta-service` block |
| `docker/docker-compose.yml` `kafka-init` | Add `gps-cleaned` Kafka topic (currently missing from init) |

### `docker/init/01-databases.sql` addition

```sql
CREATE DATABASE eta_db;
```

### `docker-compose.yml` eta-service env addition

```yaml
ETA_DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/eta_db
```

---

## Phase 4 — ETA Service: off-route guard + persistence

### Files changed

| File | Change |
|------|--------|
| `services/eta-service/models/eta_record.py` | NEW — SQLAlchemy ORM model |
| `services/eta-service/models/eta_db.py` | NEW — engine + `init_db()` + `get_session()` |
| `services/eta-service/consumer.py` | Off-route guard + DB insert after Redis write |
| `services/eta-service/main.py` | Call `init_db()` in FastAPI lifespan |
| `services/eta-service/requirements.txt` | Add `psycopg2-binary`, `sqlalchemy>=2.0` |

### `eta_records` table schema

To efficiently manage high-frequency telemetry storage without heavy cron `DELETE` jobs, the table uses PostgreSQL partitioning by month. This is defined via a lightweight Alembic setup specifically inside `services/eta-service/`.

```sql
CREATE TABLE eta_records (
  id            SERIAL,
  trip_id       TEXT        NOT NULL,
  bus_id        TEXT        NOT NULL,
  route_id      TEXT,
  stop_id       INTEGER,
  eta_seconds   FLOAT       NOT NULL,
  distance_m    FLOAT       NOT NULL,
  speed_ms      FLOAT       NOT NULL,
  model_used    TEXT        NOT NULL,  -- 'physics' | 'xgboost' | 'sarima'
  clamped       BOOLEAN     NOT NULL DEFAULT false,
  off_route     BOOLEAN     NOT NULL DEFAULT false,
  timestamp     TIMESTAMPTZ NOT NULL,  -- from GPS message
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Example partition creation (managed by automation/Alembic)
CREATE TABLE eta_records_y2026m05 PARTITION OF eta_records 
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE INDEX eta_records_route_stop_idx ON eta_records (route_id, stop_id, timestamp);
CREATE INDEX eta_records_trip_idx       ON eta_records (trip_id, timestamp);
```

### Off-route guard in `consumer.py`

```python
if payload.get("offRoute"):
    logger.warning(
        "Skipping ETA for off-route bus %s (trip %s, deviation %.1f m)",
        payload.get("busId"), payload.get("tripId"),
        payload.get("offRouteDistanceM", 0.0),
    )
    return {"skipped": True, "reason": "off_route"}
```

- No Redis snapshot update.
- No `eta:live` publish.
- No `eta_records` insert.
- Downstream: WebSocket clients see no update (stale ETA retained until TTL 300 s or trip ends).

### DB insert (non-blocking)

```python
try:
    eta_db.insert_record(snapshot, stop_id=event.next_stop_id, off_route=False)
except Exception as exc:
    logger.error("eta_db insert failed (non-fatal): %s", exc)
    # Real-time path continues regardless
```

---

## Phase 5 — SARIMA Time-Series ETA Forecasting

### Files changed

| File | Change |
|------|--------|
| `services/eta-service/models/training/train_sarima.py` | NEW — offline CLI training script |
| `services/eta-service/models/sarima_eta.py` | NEW — forecast function |
| `services/eta-service/routers/eta.py` | Add `?model=sarima` branch |
| `services/eta-service/requirements.txt` | Add `statsmodels>=0.14` |
| `services/eta-service/tests/unit/test_sarima_eta.py` | NEW — unit tests |

### Why SARIMA?

`eta_records` for a given `(route_id, stop_id)` pair forms a time series of observed ETA values
indexed by `timestamp`. Bus dwell patterns exhibit:

- **Daily seasonality (S=24)**: rush-hour spikes at 7–9 am and 5–7 pm every weekday.
- **Weekly seasonality**: weekends have lower and more uniform ETAs.

SARIMA `(p=1, d=1, q=1)(P=1, D=1, Q=1, S=24)` captures both. XGBoost handles these via
engineered features; SARIMA captures them directly from the history of observations and is
therefore better suited when the input is a temporal sequence rather than a feature vector.

### `train_sarima.py` workflow

All constants like minimum training threshold are loaded as environment variables via `app/config.py` (e.g., `SARIMA_MIN_THRESHOLD_HOURS=48`). We keep the 48-hour requirement to ensure 2 full seasonal cycles and avoid skew from single-day anomalies like public holidays.

```
1. SELECT trip_id, stop_id, route_id, eta_seconds, timestamp
   FROM eta_records
   WHERE off_route = false
   ORDER BY timestamp

2. Group by (route_id, stop_id)

3. For each group with ≥ 48 hours of data (SARIMA_MIN_THRESHOLD_HOURS):
   a. Resample to hourly mean ETA
   b. Fit SARIMA(1,1,1)(1,1,1,24)
   c. Save: sarima_artifacts/{route_id}_{stop_id}.joblib
   d. Print AIC, RMSE on hold-out last 24 h

4. Exit 0 on success; exit 1 if any group fails to converge
```

### `sarima_eta.forecast_eta_sarima(route_id, stop_id, dt)`

```python
@lru_cache(maxsize=128)
def _load_artifact(route_id, stop_id): ...   # loads joblib, None if missing

def forecast_eta_sarima(route_id, stop_id, dt=None) -> float | None:
    model = _load_artifact(route_id, stop_id)
    if model is None:
        return None    # caller falls back to XGBoost / physics
    dt = dt or datetime.now()
    forecast = model.predict(start=dt, end=dt)
    return float(max(0.0, forecast.iloc[0]))
```

### HTTP endpoint addition

```
GET /api/v1/eta/{tripId}/{stopId}?model=sarima

Response 200 (artifact available):
  { "model_used": "sarima", "eta_seconds": 118.3, ... }

Response 200 (no artifact — graceful fallback):
  { "model_used": "physics", "eta_seconds": 120.5, ... }
```

---

## Verification Checklist

### Infrastructure
- [ ] `docker exec ontime_postgres psql -U postgres -c "\l"` → `eta_db` listed
- [ ] `docker exec ontime_postgres psql -U postgres -d eta_db -c "\dt"` → `eta_records` table exists

### Phase 1 — `offRoute` field
- [ ] `pytest services/stream-processing/tests/unit/test_enrichment.py -v` → all pass (incl. `offRoute` tests)
- [ ] Enriched message on `gps-cleaned` contains `offRoute`, `offRouteDistanceM`

### Phase 2 — Anomaly streak
- [ ] `pytest services/anomaly-service/tests/ -v` → streak tests pass
- [ ] Run GPS simulator with bus off-route for 3+ readings → `transport-anomaly-alerts` contains `PERSISTENT_OFF_ROUTE`

### Phase 4 — ETA persistence
- [ ] `pytest services/eta-service/tests/ -v` → all pass + new guard/persist tests
- [ ] On-route message → `eta_records` row inserted
- [ ] Off-route message → no row in `eta_records`, no `eta:live` publish

### Phase 5 — SARIMA
- [ ] `pytest services/eta-service/tests/unit/test_sarima_eta.py -v`
- [ ] `python3 services/eta-service/models/training/train_sarima.py` → artifacts in `sarima_artifacts/`
- [ ] `GET /api/v1/eta/TRIP-001/42?model=sarima` → `model_used: sarima` or graceful fallback

---

## Scope Boundaries

- `transport-telemetry-cleaned` consumers (Anomaly Service, InfluxDB) are **not broken** — `offRoute` is additive.
- WebSocket Service requires **no changes** — it subscribes to `eta:live` unchanged.
- SARIMA training is **offline/manual** — `train_sarima.py` is a CLI script, not a background task.
- The XGBoost pipeline (K-7–K-10, PR #92) is **not replaced** — SARIMA is an additional `?model=sarima` option.
- `eta_db` is on the same Postgres container; no new Docker service needed.

---

## Resolved Questions (from CR1 Review)

1. **`eta_records` retention policy**: We will use **Postgres table partitioning by month**. This is vastly more efficient for high-frequency telemetry than a cron `DELETE` job.
2. **SARIMA minimum sample threshold**: Kept at **48 hours (2 cycles)** to avoid skewed models from single-day anomalies (e.g., public holidays). Configured via Env Var.
3. **Off-route streak threshold**: A **time-based 5-second sliding window** is used instead of a fixed ping count. Configured via Env Var.
4. **`eta_db` schema ownership**: Will use a **lightweight Alembic** configuration placed directly inside `services/eta-service/`.
5. **Hardcoded Numbers**: All constants (thresholds, windows, retention logic) must be moved to `app/config.py` and loaded dynamically via Environment Variables.
