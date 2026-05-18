import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.endpoints import router
from app.database.connection import init_db
from app.consumers.crowd_report_consumer import CrowdReportConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

consumer = CrowdReportConsumer()
stop_event = threading.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    init_db()
    
    # Start Kafka Consumer in background thread
    consumer_thread = threading.Thread(target=consumer.consume_forever, args=(stop_event,), daemon=True)
    consumer_thread.start()
    
    yield
    
    # Shutdown
    stop_event.set()
    consumer_thread.join(timeout=2.0)
    logger.info("Service shutdown gracefully")

app = FastAPI(title="Crowd Sensing Service", lifespan=lifespan)
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "healthy"}
