from datetime import datetime, timezone
import logging
import threading
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

from app.models.anomaly_model import AnomalyModel

_model_probe: AnomalyModel | None = None


def _isolation_forest_status() -> dict:
    global _model_probe
    if _model_probe is None:
        _model_probe = AnomalyModel()
    return {
        "loaded": _model_probe.isolation_model is not None,
        "version": _model_probe.isolation_model_version,
        "artifactPath": _model_probe.isolation_model_path,
        "primaryDetector": "isolation_forest" if _model_probe.isolation_model else "rules_fallback",
    }


def create_app():
    app = FastAPI(
        title="OnTime Anomaly Service",
        version="1.0.0",
        description="Health and metrics endpoints for the Anomaly service",
    )

    @app.get("/health")
    def health():
        if_status = _isolation_forest_status()
        return {
            "status": "healthy",
            "service": "anomaly-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": {},
            "isolationForest": if_status,
            "behavioralDetection": if_status["primaryDetector"],
        }

    @app.get("/health/live")
    def live():
        return {
            "status": "alive",
            "service": "anomaly-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/health/ready")
    def ready():
        # Minimal check for ready
        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "status": "healthy",
            "service": "anomaly-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics_endpoint():
        return "# TYPE anomaly_service_up gauge\nanomaly_service_up 1\n"

    return app

app = create_app()

def start_health_server(port=8006):
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
