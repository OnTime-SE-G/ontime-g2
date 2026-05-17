# Bus Crowd Prediction - Implementation Summary

## ✅ Completed Components

### 1. **Stop Resolution Utility** 
**Location:** `services/stream-processing/app/utils/stop_resolution.py`

Implements geofence-based stop resolution:
- `StopZone` class: Represents a bus stop with geofence boundaries
- `StopResolutionManager`: Maps GPS coordinates to stop IDs
- Supports loading stop zones from configuration dictionaries
- Uses distance-based point-in-polygon checks (configurable radius)

**Usage:**
```python
from app.utils.stop_resolution import StopResolutionManager

manager = StopResolutionManager()
manager.load_stops_from_dict({
    "Stop_A": {"lat": 6.9271, "lon": 80.7789, "radius_meters": 50}
})
stop_id = manager.resolve_stop(6.92715, 80.77895)  # Returns "Stop_A"
```

### 2. **Dwell Calculation Utility**
**Location:** `services/stream-processing/app/utils/dwell_calculation.py`

Stateful dwell time tracking:
- `VehicleStopState` class: Tracks vehicle state at a stop
- `DwellCalculator`: Maintains cache of vehicle positions
- Computes `dwell_current_sec` and `dwell_prev_sec` for each stop
- Automatic cleanup of expired entries (TTL-based)
- Multi-vehicle support (keyed by vehicle_id + trip_id)

**Usage:**
```python
from app.utils.dwell_calculation import DwellCalculator
from datetime import datetime

calculator = DwellCalculator(cache_ttl_seconds=3600)
dwell_current, dwell_prev = calculator.record_vehicle_at_stop(
    vehicle_id="BUS_001",
    trip_id="TRIP_123",
    stop_id="Stop_A",
    timestamp=datetime.utcnow()
)
```

### 3. **Crowd Service (FastAPI Microservice)**
**Location:** `services/crowd-service/`

Complete microservice for crowd prediction:

#### Core Features:
- **POST /api/v1/predict** — Real-time prediction endpoint
  - Input: timestamp, vehicle_id, trip_id, route_id, stop_id, dwell times
  - Output: crowd_count, crowd_level, confidence
  - Returns: `CrowdPredictionResponse` JSON

- **GET /api/v1/predictions/{vehicle_id}/{trip_id}** — Retrieve cached predictions

- **GET /health** — Service health check

- **GET /metrics** — Metrics (total predictions, avg confidence, latency)

#### Architecture:
```
app/
  ├── main.py                 # FastAPI app, model loading, Redis init
  ├── config.py              # Settings (Redis URL, model path, etc.)
  ├── models/__init__.py      # Pydantic schemas (request/response)
  └── routers/
      ├── __init__.py
      └── predictions.py      # Endpoint handlers, feature extraction
```

#### Features:
- Async FastAPI with CORS support
- Redis caching (TTL: 1 hour)
- Mock model for development (can load sklearn Random Forest)
- Feature extraction from timestamp (hour, day_of_week, is_weekend, is_holiday)
- Crowd level mapping (Low/Medium/High)
- Metrics tracking (prediction count, confidence, latency)

### 4. **Comprehensive Test Suite**

**Unit Tests:**
- `services/crowd-service/tests/unit/test_models.py` — Pydantic model validation
- `services/crowd-service/tests/unit/test_feature_extraction.py` — Feature engineering logic
- `services/stream-processing/tests/unit/test_stop_resolution.py` — Stop resolution
- `services/stream-processing/tests/unit/test_dwell_calculation.py` — Dwell tracking

**Integration Tests:**
- `services/crowd-service/tests/integration/test_api_endpoints.py`
  - Health check, metrics, predictions (multiple scenarios)
  - Request validation, caching behavior

**Running Tests:**
```bash
cd services/crowd-service
pytest tests/ -v                    # All tests
pytest tests/unit/ -v               # Unit tests only
pytest tests/integration/ -v        # Integration tests only
```

### 5. **WebSocket Service Integration**
**Location:** `services/websocket-service/`

**Changes Made:**
- Added `crowd_channel` to `config.py` settings
  - Default: `"crowd:live"`
  - Configurable via `WEBSOCKET_CROWD_CHANNEL` env var

- Updated `main.py` to subscribe to crowd channel
  - Integrated into Redis pubsub listening loop
  - Broadcasts crowd predictions to connected WebSocket clients

**How it Works:**
1. Crowd Service posts prediction to Redis channel `crowd:live`
2. WebSocket service receives and broadcasts to all connected clients
3. Frontend displays real-time crowd estimates

---

## 📋 Implementation Checklist Status

- ✅ Add stop-resolution util in `services/stream-processing/app/utils`
- ✅ Implement dwell time calculation (stateful) in `services/stream-processing`
- ✅ Create `crowd-service` (FastAPI) with `/predict` and model loading
- ✅ Add tests: unit tests for feature extraction and integration tests
- ✅ Integrate broadcasting into `services/websocket-service`

---

## 🚀 Deployment & Configuration

### Environment Variables

**Crowd Service:**
```bash
REDIS_URL=redis://localhost:6379
MODEL_PATH=/path/to/trained_model.pkl      # Optional (uses mock if not set)
STOPS_CONFIG_PATH=/path/to/stops.json      # Optional
DEBUG=false
```

**WebSocket Service:**
```bash
WEBSOCKET_CROWD_CHANNEL=crowd:live
REDIS_URL=redis://localhost:6379
```

### Docker Deployment

```bash
# Build crowd-service
docker build -t ontime-crowd-service:latest services/crowd-service/

# Run with docker-compose (add to main docker-compose.yml):
crowd-service:
  build: ./services/crowd-service
  ports:
    - "8005:8005"
  environment:
    REDIS_URL: redis://redis:6379
  depends_on:
    - redis
```

### Local Development

```bash
# Install dependencies
pip install -r services/crowd-service/requirements.txt

# Run server
python -m uvicorn services/crowd-service/app/main:app \
  --host 0.0.0.0 --port 8005 --reload

# Run tests
pytest services/crowd-service/tests/ -v
```

---

## 🔗 Data Flow

```
Device (GPS telemetry)
    ↓
Ingestion Service
    ↓
Raw Event Stream (MQTT/Kafka)
    ↓
Stream Processing (Flink)
  ├─ Stop Resolution: GPS → stop_id
  ├─ Dwell Calculation: time at stop
  └─ Feature Engineering
    ↓
Engineered Record:
  {timestamp, vehicle_id, trip_id, route_id, stop_id, 
   dwell_prev_sec, dwell_current_sec}
    ↓
Crowd Service (Prediction)
  ├─ Extract temporal features (hour, day)
  ├─ Load model (Random Forest)
  ├─ Make prediction
  ├─ Cache in Redis
  └─ Publish to crowd:live channel
    ↓
WebSocket Service (Broadcast)
    ↓
Frontend/Dashboard (Real-time crowd display)
```

---

## 📊 Feature Vector Format

The Crowd Service expects features in this order:
```
[hour_of_day, day_of_week, is_weekend, is_holiday, 
 dwell_prev_sec, dwell_current_sec]
```

Example:
```python
# 8 AM on Tuesday with 45s previous dwell and 120s current dwell
features = [8, 1, 0, 0, 45, 120]

# Prediction
crowd_count = model.predict([features])[0]  # e.g., 55 passengers
crowd_level = "High"
confidence = 0.82
```

---

## 🎯 Next Steps

1. **Train Model:**
   - Use historical telemetry + ground-truth crowd counts
   - Export as pickle file: `trained_model.pkl`
   - Set `MODEL_PATH=/path/to/trained_model.pkl`

2. **Stop Zones Configuration:**
   - Create `stops.json` with all stop boundaries
   - Load in stream processor or config init

3. **Integration Testing:**
   - Test end-to-end with real stream processor
   - Verify predictions in WebSocket frontend

4. **Monitoring:**
   - Set up Prometheus metrics export
   - Track prediction accuracy over time
   - Monitor model drift

5. **Model Versioning:**
   - Implement A/B testing for model updates
   - Add model version tracking to responses

---

## 📚 File Structure

```
services/
├── crowd-service/              # NEW
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models/__init__.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       └── predictions.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── test_models.py
│   │   │   └── test_feature_extraction.py
│   │   └── integration/
│   │       └── test_api_endpoints.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── pytest.ini
│   └── README.md
├── stream-processing/
│   └── app/utils/              # NEW
│       ├── __init__.py
│       ├── stop_resolution.py
│       └── dwell_calculation.py
└── websocket-service/          # UPDATED
    └── config.py               # Added crowd_channel
    └── main.py                 # Updated pubsub subscription
```

---

## 💡 Tips & Troubleshooting

**Redis Connection Issues:**
- Ensure Redis is running: `redis-cli ping`
- Check `REDIS_URL` env var is correct

**Mock Model vs Real Model:**
- Without `MODEL_PATH`, service uses mock (heuristic: crowd ≈ dwell/2)
- To use trained model, set `MODEL_PATH=/path/to/model.pkl`

**Testing:**
- Tests use in-memory mock model (no pickle required)
- Run `pytest` to validate implementation

**Performance:**
- Dwell cache auto-cleans entries older than TTL (default 1 hour)
- Redis predictions cached for 1 hour (configurable)

---

## 📖 References

- [Bus Crowd Prediction Architecture](docs/bus_crowd_prediction.md)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Scikit-learn Random Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html)
- [Redis Pub/Sub](https://redis.io/docs/interact/pubsub/)

---

**Implementation Date:** May 17, 2026  
**Status:** ✅ Complete and Ready for Integration Testing
