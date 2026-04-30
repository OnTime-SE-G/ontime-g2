from fastapi import FastAPI
from app.routers import health, buses

app = FastAPI(title="Bus Service")

app.include_router(health.router)
app.include_router(buses.router)


@app.get("/")
def root():
    return {"service": "bus-service"}