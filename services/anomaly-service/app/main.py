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
    communication_loss_check_interval_seconds: int = 60
    communication_loss_threshold_seconds: int = 180

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()


def route_geometry_to_points(route: dict) -> list[tuple[float, float]]:
    geometry = route.get("geometry")
    if not geometry:
        logger.warning("Skipping route %s because geometry is missing", route.get("id"))
        return []

    coordinates = geometry.get("coordinates")
    if not coordinates:
        logger.warning("Skipping route %s because coordinates are missing", route.get("id"))
        return []

    points = []
    for coordinate in coordinates:
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
            logger.warning("Skipping invalid coordinate for route %s: %s", route.get("id"), coordinate)
            return []
        lon, lat = coordinate[0], coordinate[1]
        points.append((lat, lon))

    return points


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
                        geometries = {}
                        for route in data:
                            if route.get("id") is None:
                                logger.warning("Skipping route geometry without id")
                                continue
                            points = route_geometry_to_points(route)
                            if points:
                                geometries[str(route["id"])] = points

                        self.route_geometries = geometries
                        logger.info(f"Loaded {len(self.route_geometries)} routes.")
                        return
                    else:
                        logger.warning(f"Failed to fetch routes (Attempt {attempt+1}/5): {response.status_code}")
            except Exception as e:
                logger.warning(f"Error fetching routes (Attempt {attempt+1}/5): {e}")
            await asyncio.sleep(5)
        logger.error("Failed to fetch route geometries after 5 attempts.")

    async def publish_alerts(self, producer: AIOKafkaProducer, alerts: list[dict]):
        for alert in alerts:
            logger.warning(f"Anomaly detected: {alert['anomalyType']} on {alert['busId']}")
            await producer.send_and_wait(
                settings.kafka_anomaly_topic,
                json.dumps(alert).encode('utf-8')
            )

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

        async def periodic_communication_loss_check():
            while True:
                await asyncio.sleep(settings.communication_loss_check_interval_seconds)
                alerts = self.model.detect_communication_loss(
                    threshold_seconds=settings.communication_loss_threshold_seconds
                )
                await self.publish_alerts(producer, alerts)

        refresh_task = asyncio.create_task(periodic_refresh())
        communication_loss_task = asyncio.create_task(periodic_communication_loss_check())

        try:
            async for msg in consumer:
                try:
                    telemetry = json.loads(msg.value.decode('utf-8'))
                    route_id = telemetry.get("routeId")
                    geometry = self.route_geometries.get(route_id, [])

                    alerts = self.model.detect(telemetry, geometry)
                    await self.publish_alerts(producer, alerts)
                except Exception as e:
                    logger.error(f"Processing error: {e}")
        finally:
            refresh_task.cancel()
            communication_loss_task.cancel()
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
