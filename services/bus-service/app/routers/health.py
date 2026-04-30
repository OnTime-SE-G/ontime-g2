from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db

router = APIRouter(
    prefix="/health",
    tags=["Health"]
)


@router.get("")
def health_check(db: Session = Depends(get_db)):
    try:
        # Simple DB check
        db.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "service": "bus-service",
            "database": "connected"
        }
    except Exception:
        return {
            "status": "error",
            "service": "bus-service",
            "database": "disconnected"
        }