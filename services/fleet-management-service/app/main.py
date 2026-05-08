from contextlib import asynccontextmanager
import time
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.database import engine
from app.models.base import Base
from app.routers import health, fleet, trips
from app.services.kafka_producer import kafka_service
from app.services.kafka_consumer import kafka_consumer_service


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

    await kafka_consumer_service.start()

    yield

    # Stop Kafka producer cleanly on shutdown
    await kafka_service.stop()
    await kafka_consumer_service.stop()


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Fleet Management Service",
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

# Instrument Prometheus metrics
Instrumentator().instrument(app).expose(app)

app.include_router(health.router)
app.include_router(fleet.router)
app.include_router(trips.router)