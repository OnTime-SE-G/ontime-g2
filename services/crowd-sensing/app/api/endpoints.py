import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from kafka import KafkaProducer
from app.config import settings
from app.schemas.crowd import CrowdReportRequest, CrowdPredictionResponse
from app.prediction.hybrid_predictor import predictor

router = APIRouter(prefix="/api/v1/crowd", tags=["Crowd Sensing"])

def get_kafka_producer():
    try:
        return KafkaProducer(
            bootstrap_servers=settings.kafka_broker_url,
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
    except Exception:
        return None

producer = get_kafka_producer()

@router.post("/report", status_code=202)
def submit_crowd_report(report: CrowdReportRequest):
    """Accept passenger crowd reports and push to Kafka for asynchronous processing."""
    if report.occupancy_score < 0 or report.occupancy_score > 100:
        raise HTTPException(status_code=400, detail="occupancy_score must be between 0 and 100")
    
    if producer:
        try:
            producer.send(settings.kafka_reports_topic, report.dict())
            producer.flush()
        except Exception as e:
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
    try:
        dt = datetime.fromisoformat(datetime_param.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    result = predictor.predict(route_id, direction_id, stop_id, dt)
    return CrowdPredictionResponse(**result)
