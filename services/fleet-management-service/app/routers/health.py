from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db

router = APIRouter(
    prefix="/health",
    tags=["Health"]
)


@router.get("")
def health_check(db: Session = Depends(get_db)):
    """Full health check including dependency statuses."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "service": "fleet-management-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "database": db_status
        }
    }


@router.get("/live")
def liveness():
    """Liveness probe — returns 200 if the process is alive."""
    return {
        "status": "alive",
        "service": "fleet-management-service",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Readiness probe — returns 200 only if DB is reachable."""
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "service": "fleet-management-service",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dependencies": {"database": "connected"}
            }
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not ready",
                "service": "fleet-management-service",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dependencies": {"database": "disconnected"}
            }
        )
