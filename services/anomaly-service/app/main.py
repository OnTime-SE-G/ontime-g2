import asyncio
import json
import logging
import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from app.models.anomaly_model import AnomalyModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILES = (
    str(REPO_ROOT / "docker" / ".env"),
    str(REPO_ROOT / "docker" / ".env.example"),
)

class Settings(BaseSettings):
    kafka_broker_url: str = "broker:29092"
    kafka_cleaned_topic: str = "transport-telemetry-cleaned"
    kafka_anomaly_topic: str = "transport-anomaly-alerts"
    route_service_url: str = "http://route-service:8002"
    
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()

class AnomalyService:
    def __init__(self):
        self.model = AnomalyModel()
        self.route_geometries = {}
        
    async def fetch_route_geometries(self):
        logger.info("Fetching route geometries...")
        for attempt in range(5):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{settings.route_service_url}/internal/routes/geometry", timeout=10.0)
                    if response.status_code == 200:
                        data = response.json()
                        self.route_geometries = {
                            str(r["id"]): [(c[1], c[0]) for c in r["geometry"]["coordinates"]] 
                            for r in data
                        }
                        logger.info(f"Loaded {len(self.route_geometries)} routes.")
                        return
                    else:
                        logger.warning(f"Failed to fetch routes (Attempt {attempt+1}/5): {response.status_code}")
            except Exception as e:
                logger.warning(f"Error fetching routes (Attempt {attempt+1}/5): {e}")
            await asyncio.sleep(5)
        logger.error("Failed to fetch route geometries after 5 attempts.")

    async def run(self):
        await self.fetch_route_geometries()
        
        consumer = AIOKafkaConsumer(
            settings.kafka_cleaned_topic,
            bootstrap_servers=settings.kafka_broker_url,
            group_id="anomaly-service-group"
        )
        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_broker_url)
        
        await consumer.start()
        await producer.start()
        logger.info("Anomaly Service running...")
        
        async def periodic_refresh():
            while True:
                await asyncio.sleep(300) # 5 minutes
                await self.fetch_route_geometries()
                
        refresh_task = asyncio.create_task(periodic_refresh())
        
        try:
            async for msg in consumer:
                try:
                    telemetry = json.loads(msg.value.decode('utf-8'))
                    route_id = telemetry.get("routeId")
                    geometry = self.route_geometries.get(route_id, [])
                    
                    alerts = self.model.detect(telemetry, geometry)
                    for alert in alerts:
                        logger.warning(f"Anomaly detected: {alert['anomalyType']} on {alert['busId']}")
                        await producer.send_and_wait(
                            settings.kafka_anomaly_topic,
                            json.dumps(alert).encode('utf-8')
                        )
                except Exception as e:
                    logger.error(f"Processing error: {e}")
        finally:
            await consumer.stop()
            await producer.stop()

if __name__ == "__main__":
    import threading
    from app.health import start_health_server
    
    # Start health server in background thread
    health_thread = threading.Thread(target=start_health_server, kwargs={"port": 8006}, daemon=True)
    health_thread.start()
    
    service = AnomalyService()
    asyncio.run(service.run())
