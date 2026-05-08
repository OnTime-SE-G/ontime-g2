# services/api-gateway/main.py
# OnTime API Gateway — FastAPI application.
# Serves health, metrics, and API endpoints for the frontend.

from fastapi import FastAPI

from app.routers import system, routes, buses, stops, admin_routes, admin_fleet, driver, trips, auth, users

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="OnTime API Gateway",
    description="G2 API gateway service for REST aggregation.",
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
app.include_router(driver.router)
app.include_router(trips.router)
app.include_router(auth.router)
app.include_router(users.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
