from fastapi import FastAPI
from app.routers import health, routes
from app.models.base import Base
from app.database import engine

# Create tables on startup (good for development)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Route Service",
    version="1.0.0",
    description="Provides route, stop, and geospatial data."
)

# Routers
app.include_router(health.router)
app.include_router(routes.router)


@app.get("/")
def root():
    return {
        "service": "route-service",
        "status": "running",
        "docs": "/docs"
    }