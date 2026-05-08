# Plan: Off-Route Detection · Persistent Anomaly · ETA Persistence · SARIMA Forecasting

**Authors:** Kusal (Lead)  
**Status:** Approved — Amendments applied per JPabasara review (PR #101)  
**Relates to:** ETA pipeline (`ETA` branch, PR #92), Inc 2

> **Review amendments (2026-05-08):** (1) SARIMA minimum threshold = 48 h (2 seasonal cycles). (2) All threshold/retention constants moved to `app/config.py` as env vars — no hardcoded numbers. (3) `eta_records` retention via PostgreSQL monthly table partitioning (not cron DELETE). (4) Anomaly L3 Isolation Forest re-specified with sliding-window feature extraction.

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
| `services/anomaly-service/app/models/anomaly_model.py` | `off_route_streak` dict + streak logic + sliding-window feature extractor for L3 |
| `services/anomaly-service/app/main.py` | All thresholds loaded from `Settings` (env vars, no hardcoded numbers) |
| `services/anomaly-service/app/config.py` | Add `OFF_ROUTE_STREAK_WINDOW_SECONDS`, `OFF_ROUTE_DISTANCE_THRESHOLD_M`, `PERSISTENT_OFF_ROUTE_THRESHOLD`, `SLIDING_WINDOW_SIZE` |
| `services/anomaly-service/tests/` | Streak unit tests + sliding-window feature-extraction tests |

### Logic

All thresholds are loaded from `app/config.py` / environment variables — no hardcoded numbers.

```
# app/config.py (env vars, all overridable)
OFF_ROUTE_DISTANCE_THRESHOLD_M   = int(os.getenv("OFF_ROUTE_DISTANCE_THRESHOLD_M",  "50"))
OFF_ROUTE_STREAK_WINDOW_SECONDS  = int(os.getenv("OFF_ROUTE_STREAK_WINDOW_SECONDS", "5"))
PERSISTENT_OFF_ROUTE_THRESHOLD   = int(os.getenv("PERSISTENT_OFF_ROUTE_THRESHOLD",  "3"))

detect(telemetry, geometry, settings):
  # use precomputed flag if Flink provides it; else compute locally (backward-compat)
  is_off = telemetry.get("offRoute") ?? (distance_to_polyline(...) > settings.OFF_ROUTE_DISTANCE_THRESHOLD_M)

  bus_id = telemetry["busId"]
  ts     = telemetry["timestamp"]          # ISO 8601 UTC

  if is_off:
    # time-based window: only count if within the configured streak window
    first_off_ts = streak_start_time.get(bus_id)
    if first_off_ts is None or (ts - first_off_ts) > settings.OFF_ROUTE_STREAK_WINDOW_SECONDS:
      streak_start_time[bus_id] = ts       # start a new window
      streak[bus_id] = 0
    streak[bus_id] += 1
    if streak[bus_id] == 1:
      emit OFF_ROUTE alert                 # existing single-hit alert (unchanged)
    if streak[bus_id] >= settings.PERSISTENT_OFF_ROUTE_THRESHOLD:
      emit PERSISTENT_OFF_ROUTE alert
  else:
    streak[bus_id] = 0                     # reset on any on-route reading
    streak_start_time.pop(bus_id, None)
```

**Why time-based window?**  
GPS fixes arrive ~1/s but are not guaranteed to be exactly 1 s apart. Using a configurable
time window (default 5 s) rather than a raw count makes the policy independent of GPS frequency
and easier to tune via environment variable without redeployment.

### New alert type

```json
{
  "anomalyType": "PERSISTENT_OFF_ROUTE",
  "message": "Bus off-route for 3 readings within 5 s window",
  "busId": "BUS-007",
  "tripId": "TRIP-2026-001",
  "routeId": "1",
  "streakCount": 3,
  "windowSeconds": 5
}
```

---

## Anomaly L3 — Isolation Forest with Sliding-Window Feature Extraction

> Added per JPabasara review: Isolation Forest requires a summary feature vector, not raw GPS pings.

### Sliding Window Design

| Parameter | Config Key | Default | Description |
|-----------|-----------|---------|-------------|
| Window size | `SLIDING_WINDOW_SIZE` | 20 | Number of recent GPS pings to include |
| Min window for inference | `SLIDING_WINDOW_MIN_SIZE` | 10 | Minimum pings before running model |
| Artifact path | `ISOLATION_FOREST_ARTIFACT_PATH` | `anomaly_model_iso.joblib` | Loaded at service startup |

### Feature Extraction from Window

Every time a new GPS ping arrives, the Anomaly Service looks at the last `SLIDING_WINDOW_SIZE`
pings and extracts a **summary vector**:

```python
def extract_window_features(window: list[dict]) -> np.ndarray:
    speeds   = [p["speed"] for p in window]       # km/h
    headings = [p.get("heading", 0) for p in window]
    # acceleration: speed delta between consecutive pings (km/h/s)
    accels   = [speeds[i] - speeds[i-1] for i in range(1, len(speeds))]

    return np.array([
        max(accels),              # max_acceleration  — flooring the gas
        min(accels),              # min_acceleration  — slamming the brakes
        np.var(speeds),           # speed_variance    — erratic speed
        np.var(headings),         # heading_variance  — swerving
        np.mean(speeds),          # mean_speed        — general pace
        max(speeds) - min(speeds) # speed_range       — swing magnitude
    ])
```

### Offline Training

```
1. Extract summary vectors from millions of normal 10–20-ping windows in historical data
2. Fit IsolationForest(n_estimators=200, contamination=0.01)
3. Save artifact: anomaly_model_iso.joblib
```

### Real-Time Inference

```python
def detect_erratic_driving(window, model, settings):
    if len(window) < settings.SLIDING_WINDOW_MIN_SIZE:
        return None   # not enough data yet
    features = extract_window_features(window[-settings.SLIDING_WINDOW_SIZE:])
    prediction = model.predict(features.reshape(1, -1))  # 1=normal, -1=anomaly
    if prediction[0] == -1:
        emit ERRATIC_DRIVING alert
```

### New alert type: `ERRATIC_DRIVING`

```json
{
  "anomalyType": "ERRATIC_DRIVING",
  "message": "Isolation Forest detected erratic driving pattern (speed_variance=12.5, heading_variance=45.0)",
  "busId": "BUS-007",
  "tripId": "TRIP-2026-001",
  "features": {
    "max_acceleration": 4.2,
    "min_acceleration": -5.1,
    "speed_variance": 12.5,
    "heading_variance": 45.0,
    "mean_speed": 28.3,
    "speed_range": 18.6
  }
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

> **Retention strategy (per JPabasara review):** Use PostgreSQL declarative table partitioning by
> month. This is vastly more efficient for high-frequency telemetry than a cron DELETE job:
> dropping a partition is an O(1) metadata operation vs. a full table scan DELETE.

```sql
-- Parent partitioned table (no rows stored directly)
CREATE TABLE eta_records (
  id            BIGSERIAL,
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
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (recorded_at);

-- Monthly partitions — new ones created automatically by maintenance script
CREATE TABLE eta_records_2026_05 PARTITION OF eta_records
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE eta_records_2026_06 PARTITION OF eta_records
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

-- Indexes defined on parent; PostgreSQL propagates to all partitions
CREATE INDEX eta_records_route_stop_idx ON eta_records (route_id, stop_id, recorded_at);
CREATE INDEX eta_records_trip_idx       ON eta_records (trip_id, recorded_at);

-- Retention: drop month partitions older than configured retention window
-- No DELETE scan needed — DROP TABLE eta_records_YYYY_MM is instant
```

**Retention config (app/config.py):**

```python
ETA_RECORDS_RETENTION_MONTHS = int(os.getenv("ETA_RECORDS_RETENTION_MONTHS", "6"))
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

```
1. SELECT trip_id, stop_id, route_id, eta_seconds, timestamp
   FROM eta_records
   WHERE off_route = false
   ORDER BY timestamp

2. Group by (route_id, stop_id)

3. For each group with ≥ SARIMA_MIN_HOURS hourly samples (default 48 h = 2 full seasonal cycles of S=24):
   a. Resample to hourly mean ETA
   b. Fit SARIMA(1,1,1)(1,1,1,24)
   c. Save: sarima_artifacts/{route_id}_{stop_id}.joblib
   d. Print AIC, RMSE on hold-out last 24 h

4. Exit 0 on success; exit 1 if any group fails to converge

**Why 48 h (not 24 h)?**  
A single 24-hour day may be a public holiday, an incident day, or an atypical weekday — all of
which would skew the seasonal baseline. Two complete cycles (48 h) guarantees the model has
seen at least one full weekday pattern and reduces the risk of a holiday biasing the estimate.

**Config key (app/config.py):**

```python
SARIMA_MIN_HOURS = int(os.getenv("SARIMA_MIN_HOURS", "48"))
```
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

## Configuration Reference

All constants that were previously hardcoded are now environment variables loaded via `app/config.py`:

| Env Var | Service | Default | Description |
|---------|---------|---------|-------------|
| `OFF_ROUTE_DISTANCE_THRESHOLD_M` | anomaly-service | `50` | Metres from polyline before bus is considered off-route |
| `OFF_ROUTE_STREAK_WINDOW_SECONDS` | anomaly-service | `5` | Time window for consecutive off-route readings |
| `PERSISTENT_OFF_ROUTE_THRESHOLD` | anomaly-service | `3` | Min readings in window to trigger PERSISTENT_OFF_ROUTE |
| `SLIDING_WINDOW_SIZE` | anomaly-service | `20` | GPS pings in sliding window for L3 Isolation Forest |
| `SLIDING_WINDOW_MIN_SIZE` | anomaly-service | `10` | Min pings before L3 inference runs |
| `ISOLATION_FOREST_ARTIFACT_PATH` | anomaly-service | `anomaly_model_iso.joblib` | L3 model artifact |
| `SARIMA_MIN_HOURS` | eta-service | `48` | Min hours of hourly ETA history before SARIMA trains |
| `ETA_RECORDS_RETENTION_MONTHS` | eta-service | `6` | Monthly partitions older than this are dropped |
| `ETA_DATABASE_URL` | eta-service | (required) | PostgreSQL connection string for eta_db |

---

## Scope Boundaries

- `transport-telemetry-cleaned` consumers (Anomaly Service, InfluxDB) are **not broken** — `offRoute` is additive.
- WebSocket Service requires **no changes** — it subscribes to `eta:live` unchanged.
- SARIMA training is **offline/manual** — `train_sarima.py` is a CLI script, not a background task.
- The XGBoost pipeline (K-7–K-10, PR #92) is **not replaced** — SARIMA is an additional `?model=sarima` option.
- `eta_db` is on the same Postgres container; no new Docker service needed.

---

## Open Questions for Review

1. **`eta_records` retention policy** — With 1 GPS fix/s per bus across many trips, the table grows
   quickly. Should we add `DELETE WHERE recorded_at < NOW() - INTERVAL '90 days'` as a cron job,
   or rely on Postgres partitioning by month? Preference?

2. **SARIMA minimum sample threshold (48)** — Is 48 h of data (2 seasonal cycles) a reasonable
   minimum before the model activates, or should it be lower (e.g., 24 h for one cycle)?

3. **Off-route streak threshold (3)** — GPS fixes arrive ~1 s apart in our simulator. Should the
   threshold be a count (3 readings) or a time window (e.g., 5 s of consecutive off-route)?

4. **`eta_db` schema ownership** — Using `create_all()` at startup is simple but means rollbacks
   require manual `DROP TABLE`. Should we add a lightweight Alembic setup inside
   `services/eta-service/` instead (consistent with how route-service uses the root Alembic)?
