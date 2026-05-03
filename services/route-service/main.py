from fastapi import FastAPI

from .routers import routes, buses

app = FastAPI(title="OnTime Route Service", version="1.0.0")

app.include_router(routes.router)
app.include_router(buses.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "route-service"}
