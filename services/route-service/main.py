from fastapi import FastAPI

from routers.health import router as health_router
from routers.routes import router as routes_router

app = FastAPI(
    title="OnTime Route Service",
    version="0.1.0",
    description="Route management microservice."
)

app.include_router(health_router)
app.include_router(routes_router)