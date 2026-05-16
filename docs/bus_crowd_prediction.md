# Bus Crowd Prediction — Architecture & Implementation Guide

## Overview
This document refines the provided model plan and adapts it to this repository's service layout. It describes the data schema, feature engineering, runtime inference flow, edge-case handling, and a concise implementation checklist so the team can integrate crowd predictions into the existing microservices.

## 1. Model Summary
- Algorithm: Random Forest
  - Use a Regressor for exact counts and a Classifier for Low/Medium/High categories.
  - Advantages: handles mixed features, interpretable, robust to outliers.

## 2. Data Schema & Feature Mapping (project-specific)
The repo collects GPS, timestamps, trip lifecycle events and dwell-related signals across `services/ingestion` and `services/stream-processing`. Map those inputs to the features below.

- Temporal features
  - `timestamp` (ISO8601) — source: `services/ingestion/app/main.py` payloads
  - `hour_of_day` (int 0-23)
  - `day_of_week` (int 0-6)
  - `is_weekend` (0/1)
  - `is_holiday` (0/1) — optional external lookup (calendar service or static table)

- Spatial features
  - `gps_lat`, `gps_lon` — incoming from MQTT payloads
  - `stop_id` (categorical) — resolved by geofence/stop-mapping
    - Implementation hint: maintain a `stop_zones` table or geohash map in `services/route-service` or `schemas/geo_config.py`.

- Behavioral (dwell/time lap stayed at the bus hold) features — core predictors
  - `dwell_current_sec` — seconds spent at the current stop while boarding/alighting
  - `dwell_prev_sec` — dwell at previous stop
  - `dwell_moving_pause_sec` — short stop due to traffic (to be filtered)

- Target
  - `crowd_count` (int) OR `crowd_level` (Low / Medium / High)

Example CSV/training columns:

Timestamp,vehicle_id,route_id,stop_id,hour_of_day,day_of_week,is_weekend,is_holiday,dwell_prev_sec,dwell_current_sec,crowd_count

## 3. Feature Extraction Implementation (where to add code)
- Ingestion: `services/ingestion/app/mqtt_subscriber.py` and `services/ingestion/app/validator.py`
  - Parse timestamps, validate GPS, attach `vehicle_id` and `trip_id`.
  - Emit normalized events to the internal topic (e.g., Kafka/MQTT topic for downstream).

- Stop resolution: add a small utility that uses stop polygons or geohash to resolve `stop_id` from `(lat,lon)`.
  - Candidate locations: `services/route-service/app/` or a new helper in `services/stream-processing/app/utils`.

- Dwell calculation: maintain a short-lived cache in ingestion (or stream processing) keyed by `vehicle_id` + `trip_id` to compute stop-entry and stop-exit timestamps.
  - For example: `trip_lifecycle_cache.py` in `services/ingestion/app/` already exists and is a good integration point.

## 4. Real-Time Inference Flow (mapped to services)
1. Device -> `services/ingestion` (MQTT HTTP) — publishes normalized event: `{timestamp, vehicle_id, gps, door_status}`.
2. Ingestion resolves `stop_id` and computes `dwell_current_sec` and reads `dwell_prev_sec` from short cache.
3. Ingestion pushes engineered record to stream processor (Flink job in `services/stream-processing/app/job.py`) or to a lightweight model endpoint.
4. Model endpoint (`crowd-service` or integrated into `services/eta-service`) receives the feature vector and returns prediction.
5. Broadcast: predictions published to the websocket service (`services/websocket-service/main.py`) and stored in a short-term cache for dashboard queries.

Deployment options
- Option A — New microservice: `crowd-service`
  - Pros: clear separation, independent scaling, easy model updates
  - Cons: one more container to manage

- Option B — Integrate into `services/eta-service` or `services/stream-processing`
  - Pros: reuse existing infra, lower operational overhead
  - Cons: tighter coupling, potential resource contention

## 5. API & Schema (recommended)
- POST /predict
  - Payload: { "timestamp": "...", "vehicle_id": "...", "stop_id": "...", "hour_of_day": 8, "day_of_week": 1, "dwell_prev_sec": 45, "dwell_current_sec": 120 }
  - Response: { "crowd_count": 55, "crowd_level": "High", "confidence": 0.82 }

Implementation: implement a small FastAPI app (match repo style) or a simple Flask endpoint in `services/crowd-service/app/main.py`.

## 6. Edge Cases & Data Quality Rules (concrete)**
- Geofence-only dwell: count `dwell` only when the vehicle is inside a stop polygon and `door_status=open` or the hardware signal indicates boarding.
- Traffic vs. Dwell: ignore stationary intervals outside stop polygons or when `door_status` is closed for > 3s.
- Cap long dwell: if `dwell_current_sec > 300`, flag as `terminal_layover` and either cap at 300 or mark record with `special_dwell=True` and exclude from training.
- Impute missing `dwell_prev_sec` with median dwell for that stop/time window during training and keep a runtime fallback in the model service.

## 7. Training & Evaluation Notes
- Training dataset: combine historical telemetry with ground-truth crowd counts (from farebox sensors or manual counts).
- Feature encoding: one-hot or ordinal encode `stop_id` (or use embedding if many stops). Random Forest in scikit-learn handles categorical via ordinal encoding; for many categories consider hashing or target encoding.
- Evaluation metrics: MAE / RMSE for counts; accuracy / F1 for categorical levels. Track per-route and per-hour metrics.

## 8. Minimal Implementation Checklist (next actions)
- [ ] Add stop-resolution util in `services/stream-processing/app/utils` or `services/route-service`
- [ ] Extend `services/ingestion` to compute and emit `dwell_prev_sec` and `dwell_current_sec`
- [ ] Create `crowd-service` (FastAPI) with `/predict` and model loading
- [ ] Add tests: unit tests for feature extraction and integration tests for end-to-end inference (place under services/crowd-service/tests)
- [ ] Integrate broadcasting into `services/websocket-service`

## 9. Storage & Observability
- Short-term cache: Redis for latest predictions per `vehicle_id`/`trip_id`.
- Long-term training store: append engineered rows to S3/CSV or a DB table for batch retraining.
- Monitoring: expose Prometheus metrics for request counts, latencies, model confidence distribution.

## 10. Quick Example: training CSV header
timestamp,vehicle_id,trip_id,route_id,stop_id,hour_of_day,day_of_week,is_weekend,is_holiday,dwell_prev_sec,dwell_current_sec,crowd_count

---
File created: `docs/bus_crowd_prediction.md`

If you want, I can scaffold `services/crowd-service` (FastAPI), add stop-resolution utility, or implement ingestion changes next.
