# services/route-service/main.py

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import health, routes, admin_routes, internal
from app.models.base import Base
from app.database import engine
from app.schemas import ServiceMetadataResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic with retry
    for attempt in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database ready")
            break
        except Exception:
            print(f"Waiting for database... {attempt + 1}/10")
            time.sleep(3)
    else:
        raise RuntimeError("Database not available")

    yield

    # Shutdown logic (optional)
    print("Shutting down Route Service")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Route Service",
    version="1.0.0",
    description="Provides route, stop, and geospatial data.",
    lifespan=lifespan
)

origins = [
    "http://on-time.live",
    "https://on-time.live",
    "http://admin.on-time.live",
    "https://admin.on-time.live",
    "http://driver.on-time.live",
    "https://driver.on-time.live",
    "http://grafana.on-time.live",
    "https://grafana.on-time.live",
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(routes.router)
app.include_router(admin_routes.router)
app.include_router(internal.router)


@app.get("/", response_model=ServiceMetadataResponse)
def root():
    """
    Return basic route-service metadata.

    Use this endpoint to confirm the service is running and to discover
    the interactive API documentation path.
    """
    return {
        "service": "route-service",
        "status": "running",
        "docs": "/docs"
    }
