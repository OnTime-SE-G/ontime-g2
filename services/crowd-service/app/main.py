"""
Crowd Service - Main FastAPI Application

Provides real-time bus crowd level predictions using Random Forest model.
Receives engineered features from stream processor and returns crowd estimates.
"""

import logging
import json
import pickle
from contextlib import asynccontextmanager
from datetime import datetime
from time import time
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.config import Settings
from app.models import CrowdPredictionRequest, CrowdPredictionResponse, HealthResponse, MetricsResponse
from app.routers import predictions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()

# Global state
_redis_client: Optional[Redis] = None
_model: Optional[object] = None
_request_stats = {
    "total_predictions": 0,
    "total_latency_ms": 0.0,
    "min_confidence": 1.0,
    "max_confidence": 0.0,
    "confidences": []
}


async def initialize_model() -> object:
    """Load the trained Random Forest model from disk."""
    global _model
    
    if settings.model_path is None:
        logger.warning("MODEL_PATH not set. Using mock model for testing.")
        # Return a simple mock model for development
        _model = _MockCrowdModel()
        return _model
    
    try:
        with open(settings.model_path, "rb") as f:
            _model = pickle.load(f)
        logger.info(f"Loaded model from {settings.model_path}")
        return _model
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        _model = _MockCrowdModel()
        return _model


async def initialize_redis() -> Redis:
    """Initialize Redis connection."""
    global _redis_client
    
    class _InMemoryRedis:
        """A tiny async in-memory Redis-like fallback for tests and dev.

        Implements minimal methods used by this service: `ping`, `setex`, `get`,
        and `aclose`.
        """
        def __init__(self):
            self.store = {}

        async def ping(self):
            return True

        async def setex(self, key, ttl, value):
            self.store[key] = value

        async def set(self, key, value):
            self.store[key] = value

        async def get(self, key):
            return self.store.get(key)

        async def aclose(self):
            return None

    try:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        await _redis_client.ping()
        logger.info(f"Connected to Redis: {settings.redis_url}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Failed to connect to Redis ({settings.redis_url}): {e}. Using in-memory fallback.")
        _redis_client = _InMemoryRedis()
        return _redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown."""
    # Startup
    logger.info("Starting Crowd Service")
    await initialize_redis()
    await initialize_model()
    yield
    
    # Shutdown
    logger.info("Shutting down Crowd Service")
    if _redis_client:
        await _redis_client.aclose()


app = FastAPI(
    title="OnTime Crowd Prediction Service",
    description="Real-time bus crowd level prediction service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(predictions.router, prefix="/api/v1", tags=["predictions"])


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service_name=settings.service_name,
        version="1.0.0"
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Get service metrics."""
    avg_confidence = (
        sum(_request_stats["confidences"]) / len(_request_stats["confidences"])
        if _request_stats["confidences"] else 0.0
    )
    avg_latency = (
        _request_stats["total_latency_ms"] / _request_stats["total_predictions"]
        if _request_stats["total_predictions"] > 0 else 0.0
    )
    
    return MetricsResponse(
        total_predictions=_request_stats["total_predictions"],
        average_confidence=avg_confidence,
        prediction_latency_ms=avg_latency
    )


class _MockCrowdModel:
    """Mock model for development and testing."""
    
    def predict(self, features):
        """Return mock predictions."""
        # Simple heuristic: crowd count based on dwell time
        # features = [hour, day, dwell_prev, dwell_current, ...]
        dwell_current = features[3] if len(features) > 3 else 0
        
        # Map dwell to crowd estimate
        crowd_count = min(100, max(5, int(dwell_current / 2)))
        return [crowd_count]
    
    def predict_proba(self, features):
        """Return mock probabilities for classification."""
        return [[0.3, 0.4, 0.3]]  # [Low, Medium, High]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=settings.debug)
