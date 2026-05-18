# ETA Service

The ETA Service computes estimated arrival times for the OnTime G2 platform using a hybrid machine learning pipeline and streaming analytics. It ingests enriched telemetry from Flink via Kafka, processes it through a smoothing window, and passes the state to an intelligent cascade of prediction models.

## Microservice Architecture (CR2 Fortification)

The ETA Service uses a robust prediction cascade and memory-safe stream processing:

1. **Stateful Stream Processing**: 
   - A `collections.deque`-based sliding window averages recent bus speeds (configurable window size).
   - **TTL Filtering**: Stale GPS events older than the TTL are automatically discarded before averaging.
   - **Memory Cleanup**: Explicit `TRIP_ENDED` event detection safely drops trip state memory, preventing memory leaks.

2. **Model Cascade**: 
   - **Primary**: XGBoost ML model (fetches `.joblib` artifacts built via MLflow).
   - **Secondary (Fallback)**: SARIMA statistical forecasting (used when ML predictions are too erratic or out of bounds).
   - **Failsafe**: Deterministic Physics model ($T = D/S$), used if data is completely unavailable or ML/SARIMA fails.

3. **Data Outputs**: 
   - Publishes live ETAs to the Redis `eta:live` Pub/Sub channel for the WebSocket Service.
   - Persists historical predictions into a PostgreSQL database (with partitioning) for downstream analytics and model retraining.

## Repository Structure

Standardized for G2 Microservices:
- `app/api/`: FastAPI HTTP endpoints (e.g., `/health`, `/metrics`).
- `app/consumers/`: Kafka consumer (`eta_consumer.py`) handling the data ingestion and smoothing.
- `app/database/`: SQLAlchemy ORM models, repository, and connection helpers.
- `app/prediction/`: The XGBoost -> SARIMA -> Physics cascade and routing logic.
- `app/schemas/`: Pydantic data validation schemas.
- `app/training/`: Offline ML model training scripts and artifact generation.
- `app/config.py`: Unified Pydantic settings loading.

## Configuration (Environment Variables)

All configuration is managed through Pydantic in `app/config.py`.

| Variable | Description | Default |
|---|---|---|
| `ETA_SERVICE_PORT` | FastAPI service port | `8005` |
| `ETA_DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/eta_db` |
| `ETA_KAFKA_BROKER_URL` | Kafka bootstrap server | `broker:29092` |
| `ETA_KAFKA_TOPIC` | Kafka source topic from Flink | `transport-eta-features` |
| `ETA_LIVE_CHANNEL` | Redis Pub/Sub channel | `eta:live` |
| `ETA_DEFAULT_MODEL` | Default starting model in cascade | `xgboost` |
| `ETA_SMOOTHING_WINDOW_SIZE` | CR2: Moving average event limit | `10` |
| `ETA_SMOOTHING_TTL_SECONDS` | CR2: Max age of cached events | `120` |
| `ETA_MLFLOW_TRACKING_URI` | URI for fetching ML artifacts | `http://mlflow:5000` |
| `ETA_SARIMA_MIN_HOURS` | Minimum history for SARIMA | `48` |

## ETA Message Output Contract

When the consumer publishes to `eta:live`, the WebSocket service expects this exact JSON structure:

```json
{
  "event": "eta_update",
  "tripId": "TRIP-001",
  "busId": "1",
  "routeId": "202",
  "stopId": 42,
  "stopName": "Central Station",
  "eta_seconds": 120.5,
  "model_used": "xgboost",
  "model_version": "v2.1",
  "routeProgressPct": 45.5,
  "distanceToNextStop": 234.5,
  "timestamp": "2026-05-18T01:00:00Z"
}
```

## Running the Service

The service runs entirely inside Docker Compose in the standard G2 pipeline:
```bash
docker-compose up --build eta-service
```
*(The FastAPI web server runs on the foreground, while the Kafka consumer is launched as a background thread on startup.)*

