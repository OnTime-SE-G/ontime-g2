# services/eta-service/main.py
# OnTime ETA Service — dedicated microservice for ETA prediction.
# Owns all AI/physics ETA logic; the API Gateway proxies to this service.

import os
from datetime import datetime, timezone
from typing import Dict

from fastapi import FastAPI

from routers import eta as eta_router

app = FastAPI(
    title="OnTime ETA Service",
    version="0.1.0",
    description="Dedicated microservice for bus ETA prediction (AI + physics).",
)

app.include_router(eta_router.router)

SERVICE_START_TIME = datetime.now(timezone.utc)


@app.get("/health")
def health() -> Dict[str, object]:
    return {
        "status": "healthy",
        "service": "eta-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
