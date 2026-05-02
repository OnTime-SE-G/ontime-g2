# services/api-gateway/main.py
# OnTime API Gateway — FastAPI application.
# Serves health, metrics, and API endpoints for the frontend.

from fastapi import FastAPI

from app.routers import system, routes, buses, stops, admin_routes, admin_fleet

app = FastAPI(
    title="OnTime API Gateway",
    version="0.1.0",
    description="G2 API gateway service for REST and WebSocket endpoints.",
)

app.state.request_count = 0

@app.middleware("http")
async def count_requests(request, call_next):
    response = await call_next(request)
    request.app.state.request_count += 1
    return response

app.include_router(system.router)
app.include_router(routes.router)
app.include_router(buses.router)
app.include_router(stops.router)
app.include_router(admin_routes.router)
app.include_router(admin_fleet.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
