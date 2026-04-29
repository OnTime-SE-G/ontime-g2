import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import health, routes, admin_routes
from app.models.base import Base
from app.database import engine


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


app = FastAPI(
    title="Route Service",
    version="1.0.0",
    description="Provides route, stop, and geospatial data.",
    lifespan=lifespan
)

app.include_router(health.router)
app.include_router(routes.router)
app.include_router(admin_routes.router)


@app.get("/")
def root():
    return {
        "service": "route-service",
        "status": "running",
        "docs": "/docs"
    }