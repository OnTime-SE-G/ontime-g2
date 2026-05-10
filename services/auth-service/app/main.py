from fastapi import FastAPI
from .routers import auth, users
from .database import engine, Base
from .config import settings

from contextlib import asynccontextmanager

import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup with retry
    for attempt in range(10):
        try:
            Base.metadata.create_all(bind=engine)
            print("Database ready (auth)")
            break
        except Exception:
            print(f"Waiting for database... {attempt + 1}/10")
            time.sleep(3)
    else:
        raise RuntimeError("Database not available")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="User management and authentication service for OnTime G2",
    lifespan=lifespan
)

app.include_router(auth.router)
app.include_router(users.router)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "auth-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
