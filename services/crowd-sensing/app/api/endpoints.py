import json
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from kafka import KafkaProducer
from app.config import settings
from app.schemas.crowd import CrowdReportRequest, CrowdPredictionResponse
from app.prediction.hybrid_predictor import predictor
from app.utils.validation import validate_route_stop

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/crowd", tags=["Crowd Sensing"])

_producer = None

def get_kafka_producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        _producer = KafkaProducer(
            bootstrap_servers=settings.kafka_broker_url,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=5000,
        )
        logger.info("Kafka producer initialized successfully.")
        return _producer
    except Exception as e:
        logger.error(f"Failed to initialize Kafka producer: {e}")
        return None

@router.post("/report", status_code=202)
def submit_crowd_report(report: CrowdReportRequest):
    """Accept passenger crowd reports and push to Kafka for asynchronous processing."""
    if report.occupancy_score < 0 or report.occupancy_score > 100:
        raise HTTPException(status_code=400, detail="occupancy_score must be between 0 and 100")
    
    producer = get_kafka_producer()
    if producer:
        try:
            producer.send(settings.kafka_reports_topic, report.dict())
            producer.flush()
        except Exception as e:
            global _producer
            _producer = None
            raise HTTPException(status_code=500, detail=f"Failed to publish report: {e}")
    else:
        raise HTTPException(status_code=503, detail="Message broker unavailable")
    
    return {"status": "accepted"}

@router.get("/predict", response_model=CrowdPredictionResponse)
def get_crowd_prediction(
    route_id: int,
    stop_id: int,
    direction_id: int = Query(0),
    datetime_param: str = Query(..., alias="datetime")
):
    """Predict occupancy for a future trip segment using the hybrid model."""
    # Validate against route-service to maintain route-stop geographical integrity
    validate_route_stop(route_id, stop_id)
    
    try:
        dt = datetime.fromisoformat(datetime_param.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    result = predictor.predict(route_id, direction_id, stop_id, dt)
    return CrowdPredictionResponse(**result)
