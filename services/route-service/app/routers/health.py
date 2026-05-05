#services/route-service/app/routers/health.py

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """
    Check whether the route service is available.

    Returns a lightweight status response that can be used by load balancers,
    uptime monitors, and CI smoke tests.
    """
    return {
        "status": "ok",
        "service": "route-service"
    }
