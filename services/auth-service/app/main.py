from contextlib import asynccontextmanager
from fastapi import FastAPI
from .routers import auth, users
from .database import engine, Base
from .config import settings
from .services.kafka_producer import kafka_service

# Create database tables
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await kafka_service.start()
    yield
    await kafka_service.stop()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="User management and authentication service for OnTime G2",
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

app.include_router(auth.router)
app.include_router(users.router)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "auth-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
