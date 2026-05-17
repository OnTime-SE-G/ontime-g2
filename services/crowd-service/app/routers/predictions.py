"""Predictions router for crowd prediction endpoints."""

import logging
from datetime import datetime
from time import time

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from app.config import Settings
from app.models import CrowdPredictionRequest, CrowdPredictionResponse

logger = logging.getLogger(__name__)
router = APIRouter()

settings = Settings()


async def get_redis() -> Redis:
    """Dependency to get Redis client."""
    # Import here to avoid circular imports
    from app.main import _redis_client
    if not _redis_client:
        raise HTTPException(status_code=503, detail="Redis not available")
    return _redis_client


async def get_model():
    """Dependency to get the loaded model."""
    from app.main import _model
    if not _model:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return _model


def _extract_features_from_request(req: CrowdPredictionRequest) -> list:
    """
    Extract features for the Random Forest model.
    
    Feature order must match training dataset:
    [hour_of_day, day_of_week, is_weekend, is_holiday, 
     dwell_prev_sec, dwell_current_sec, ...]
    """
    hour_of_day = req.timestamp.hour
    day_of_week = req.timestamp.weekday()  # 0=Monday, 6=Sunday
    is_weekend = 1 if day_of_week >= 5 else 0
    is_holiday = 0  # TODO: Integrate with holiday calendar
    
    # Build feature vector
    features = [
        hour_of_day,
        day_of_week,
        is_weekend,
        is_holiday,
        req.dwell_prev_sec,
        req.dwell_current_sec,
    ]
    
    return features


def _map_crowd_count_to_level(crowd_count: int) -> str:
    """Map predicted crowd count to category."""
    if crowd_count < 20:
        return "Low"
    elif crowd_count < 50:
        return "Medium"
    else:
        return "High"


@router.post("/predict", response_model=CrowdPredictionResponse)
async def predict_crowd(
    request: CrowdPredictionRequest,
    redis: Redis = Depends(get_redis),
    model = Depends(get_model)
) -> CrowdPredictionResponse:
    """
    Predict crowd level for a bus at a specific stop.
    
    Returns:
        CrowdPredictionResponse with predicted crowd count, level, and confidence.
    """
    start_time = time()
    
    try:
        # Extract features
        features = _extract_features_from_request(request)
        
        # Make prediction
        crowd_count_prediction = model.predict([features])[0]
        crowd_count = int(crowd_count_prediction)
        
        # Map to category
        crowd_level = _map_crowd_count_to_level(crowd_count)
        
        # Get confidence (average of probabilities for the predicted category)
        probabilities = model.predict_proba([features])[0]
        category_idx = {"Low": 0, "Medium": 1, "High": 2}.get(crowd_level, 1)
        confidence = float(probabilities[category_idx])
        
        response = CrowdPredictionResponse(
            vehicle_id=request.vehicle_id,
            trip_id=request.trip_id,
            stop_id=request.stop_id,
            timestamp=request.timestamp,
            crowd_count=crowd_count,
            crowd_level=crowd_level,
            confidence=confidence
        )
        
        # Cache prediction in Redis
        cache_key = f"{settings.redis_crowd_predictions_key}:{request.vehicle_id}:{request.trip_id}"
        await redis.setex(
            cache_key,
            3600,  # 1 hour TTL
            response.model_dump_json()
        )
        
        # Update metrics
        from app.main import _request_stats
        _request_stats["total_predictions"] += 1
        latency_ms = (time() - start_time) * 1000
        _request_stats["total_latency_ms"] += latency_ms
        _request_stats["confidences"].append(confidence)
        _request_stats["min_confidence"] = min(_request_stats["min_confidence"], confidence)
        _request_stats["max_confidence"] = max(_request_stats["max_confidence"], confidence)
        
        logger.info(
            f"Prediction: vehicle={request.vehicle_id} stop={request.stop_id} "
            f"crowd={crowd_count} level={crowd_level} confidence={confidence:.2f}"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/predictions/{vehicle_id}/{trip_id}", response_model=CrowdPredictionResponse)
async def get_cached_prediction(
    vehicle_id: str,
    trip_id: str,
    redis: Redis = Depends(get_redis)
) -> CrowdPredictionResponse:
    """
    Retrieve cached prediction for a vehicle trip.
    
    Args:
        vehicle_id: The vehicle identifier
        trip_id: The trip identifier
        
    Returns:
        Cached prediction or 404 if not found
    """
    cache_key = f"{settings.redis_crowd_predictions_key}:{vehicle_id}:{trip_id}"
    cached_json = await redis.get(cache_key)
    
    if not cached_json:
        raise HTTPException(status_code=404, detail="No cached prediction found")
    
    return CrowdPredictionResponse.model_validate_json(cached_json)
