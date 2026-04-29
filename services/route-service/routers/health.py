import os
import socket
from datetime import datetime, timezone

from fastapi import APIRouter


router = APIRouter()


def can_open_tcp(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@router.get("/health")
def health():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))

    return {
        "status": "healthy",
        "service": "route-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dependencies": {
            "postgres": "up" if can_open_tcp(host, port) else "down"
        },
    }