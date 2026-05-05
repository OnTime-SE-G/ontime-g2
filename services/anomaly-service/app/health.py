from datetime import datetime, timezone
import logging
import threading
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

def create_app():
    app = FastAPI(
        title="OnTime Anomaly Service",
        version="1.0.0",
        description="Health and metrics endpoints for the Anomaly service",
    )

    @app.get("/health")
    def health():
        return {
            "status": "healthy",
            "service": "anomaly-service",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dependencies": {}
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
