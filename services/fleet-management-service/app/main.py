from contextlib import asynccontextmanager
import time
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import engine
from app.models.base import Base
from app.routers import health, fleet, trips
from app.services.kafka_producer import kafka_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database ready (fleet)")
            break
        except Exception:
            print(f"Waiting for database... {attempt + 1}/10")
            time.sleep(3)
    else:
        raise RuntimeError("Database not available")

    yield

    # Stop Kafka producer cleanly on shutdown
    await kafka_service.stop()


app = FastAPI(
    title="Fleet Management Service",
    lifespan=lifespan
)

# Instrument Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(health.router)
app.include_router(fleet.router)
app.include_router(trips.router)