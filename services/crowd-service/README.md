# Crowd Service

Real-time bus crowd level prediction microservice using Random Forest machine learning models.

## Overview

The Crowd Service predicts passenger crowd levels on buses based on:
- **Temporal features**: hour of day, day of week, holiday status
- **Behavioral features**: dwell time at current and previous stops
- **Spatial features**: bus stop location

## Features

- FastAPI-based REST API with async support
- Redis caching for prediction results
- Pluggable Random Forest model (scikit-learn)
- Comprehensive metrics and health checks
- Docker-ready deployment

## Endpoints

### Predictions
- **POST** `/api/v1/predict` — Make a crowd prediction
  - Input: timestamp, vehicle_id, trip_id, route_id, stop_id, dwell times
  - Output: crowd_count, crowd_level (Low/Medium/High), confidence

- **GET** `/api/v1/predictions/{vehicle_id}/{trip_id}` — Retrieve cached prediction

### System
- **GET** `/health` — Service health check
- **GET** `/metrics` — Prediction metrics (total predictions, average confidence, latency)

## Environment Variables

```bash
REDIS_URL=redis://localhost:6379
MODEL_PATH=/path/to/trained_model.pkl  # Optional; uses mock model if not set
STOPS_CONFIG_PATH=/path/to/stops.json  # Optional; stop zones configuration
DEBUG=false
```

## Running Locally

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
```

## Docker Build

```bash
docker build -t ontime-crowd-service:latest .
docker run -e REDIS_URL=redis://host.docker.internal:6379 -p 8005:8005 ontime-crowd-service:latest
```

## Testing

```bash
pytest tests/ -v
pytest tests/unit/ -v
pytest tests/integration/ -v
```

## Integration with Stream Processing

The Crowd Service receives engineered features from `services/stream-processing`:

1. **Stream Processor** computes:
   - Stop resolution (GPS → stop_id)
   - Dwell time calculations

2. **Crowd Service** receives the engineered record and:
   - Extracts ML features
   - Runs inference
   - Caches results in Redis
   - Publishes to WebSocket service

## Architecture

```
Device (GPS telemetry)
    ↓
Ingestion Service (raw event normalization)
    ↓
Stream Processing (stop resolution + dwell calculation)
    ↓
Crowd Service (model inference)
    ↓
WebSocket Service (broadcast to frontend)
```

## Model Training

The model expects features in this order:
```
[hour_of_day, day_of_week, is_weekend, is_holiday, 
 dwell_prev_sec, dwell_current_sec]
```

## Redis Key Format

Cached predictions:
```
crowd:predictions:{vehicle_id}:{trip_id} → JSON (TTL: 1 hour)
```

## Next Steps

- [ ] Integrate with actual trained Random Forest model
- [ ] Add stop zones configuration loader
- [ ] Implement holiday calendar lookup
- [ ] Set up model versioning and rollback
- [ ] Add Prometheus metrics export
