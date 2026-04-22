from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="OnTime API Gateway",
    description="Core interface handling WebSockets and APIs for Frontend interactions.",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    """
    Returns the basic health status of the Gateway.
    Later, this will actively ping Postgres and Redis to verify full stack health.
    """
    return JSONResponse(content={"status": "healthy", "service": "api-gateway"})

@app.get("/metrics")
async def get_metrics():
    """
    Prometheus metrics placeholder.
    """
    return {"message": "Metrics endpoint skeleton"}

if __name__ == "__main__":
    import uvicorn
    # This block allows us to run 'python main.py' locally outside of docker if needed
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
