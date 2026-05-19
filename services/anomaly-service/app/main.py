import asyncio
import json
import logging
import httpx
try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
except ImportError:  # pragma: no cover - local tests can inject producer/consumer fakes
    AIOKafkaConsumer = None
    AIOKafkaProducer = None
from app.config import settings
from app.models.anomaly_model import AnomalyModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        self.redis_client = None
        try:
            import redis

            self.redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)
        except Exception as exc:
            logger.warning("Redis anomaly live publisher unavailable: %s", exc)

        try:
            from app.models.anomaly_db import init_db

            init_db()
        except Exception as exc:
            logger.warning("anomaly_db init failed (non-fatal in dev): %s", exc)

    async def fetch_route_geometries(self):
        logger.info("Fetching route geometries...")
        for attempt in range(5):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{settings.route_service_url}/internal/routes/geometry",
                        timeout=settings.route_fetch_timeout_seconds,
                    )
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
            anomaly_type = alert.get('anomalyType', 'UNKNOWN')
            logger.warning(f"Anomaly detected: {anomaly_type} on {alert.get('busId')}")
            # Audience targeting based on config rules
            audiences = []
            if anomaly_type in [t.strip() for t in settings.anomaly_admin_types.split(",") if t.strip()]:
                audiences.append(settings.redis_anomaly_admin_channel)
            if anomaly_type in [t.strip() for t in settings.anomaly_driver_types.split(",") if t.strip()]:
                audiences.append(settings.redis_anomaly_driver_channel)
            if anomaly_type in [t.strip() for t in settings.anomaly_passenger_types.split(",") if t.strip()]:
                audiences.append(settings.redis_anomaly_passenger_channel)

            # If no audiences matched (unknown anomaly), default to admin
            if not audiences:
                audiences.append(settings.redis_anomaly_admin_channel)
            # Publish to main Kafka topic for history/processing
            await producer.send_and_wait(
                settings.kafka_anomaly_topic,
                json.dumps(alert).encode('utf-8')
            )

            # Publish to targeted Redis channels for WebSockets
            if self.redis_client is not None:
                # Remove duplicates in case a channel is added multiple times
                for channel in set(audiences):
                    try:
                        self.redis_client.publish(channel, json.dumps(alert))
                    except Exception as exc:
                        logger.error(f"Redis publish failed for {channel} (non-fatal): {exc}")

            try:
                from app.models.anomaly_db import insert_alert

                insert_alert(alert)
            except Exception as exc:
                logger.error("anomaly_db insert failed (non-fatal): %s", exc)

    async def process_cleaned_message(self, raw_value: bytes | str, producer: AIOKafkaProducer):
        telemetry = self._decode_json(raw_value)
        route_id = telemetry.get("routeId")
        geometry = self.route_geometries.get(route_id, [])

        alerts = self.model.detect(telemetry, geometry)
        await self.publish_alerts(producer, alerts)

    async def process_dlq_message(self, raw_value: bytes | str, producer: AIOKafkaProducer):
        dlq_event = self._decode_json(raw_value)
        alerts = self.model.detect_inactive_trip_dlq(
            dlq_event,
            threshold_count=settings.inactive_trip_dlq_threshold_count,
            window_seconds=settings.inactive_trip_dlq_window_seconds,
            cooldown_seconds=settings.inactive_trip_dlq_cooldown_seconds,
        )
        await self.publish_alerts(producer, alerts)

    def _decode_json(self, raw_value: bytes | str) -> dict:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode('utf-8')
        decoded = json.loads(raw_value)
        if not isinstance(decoded, dict):
            raise ValueError("Kafka message value must decode to a JSON object")
        return decoded

    async def consume_cleaned_telemetry(self, consumer: AIOKafkaConsumer, producer: AIOKafkaProducer):
        async for msg in consumer:
            try:
                await self.process_cleaned_message(msg.value, producer)
            except Exception as e:
                logger.error(f"Cleaned telemetry processing error: {e}")

    async def consume_dlq(self, consumer: AIOKafkaConsumer, producer: AIOKafkaProducer):
        async for msg in consumer:
            try:
                await self.process_dlq_message(msg.value, producer)
            except Exception as e:
                logger.error(f"DLQ processing error: {e}")

    async def run(self):
        if AIOKafkaConsumer is None or AIOKafkaProducer is None:
            raise RuntimeError("aiokafka is required to run the anomaly Kafka service")

        await self.fetch_route_geometries()

        cleaned_consumer = AIOKafkaConsumer(
            settings.kafka_cleaned_topic,
            bootstrap_servers=settings.kafka_broker_url,
            group_id=settings.kafka_cleaned_group_id
        )
        dlq_consumer = AIOKafkaConsumer(
            settings.kafka_dlq_topic,
            bootstrap_servers=settings.kafka_broker_url,
            group_id=settings.kafka_dlq_group_id
        )
        producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_broker_url)

        await cleaned_consumer.start()
        await dlq_consumer.start()
        await producer.start()
        logger.info("Anomaly Service running...")

        async def periodic_refresh():
            while True:
                await asyncio.sleep(settings.route_refresh_interval_seconds)
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
        cleaned_consumer_task = asyncio.create_task(
            self.consume_cleaned_telemetry(cleaned_consumer, producer)
        )
        dlq_consumer_task = asyncio.create_task(self.consume_dlq(dlq_consumer, producer))

        try:
            await asyncio.gather(cleaned_consumer_task, dlq_consumer_task)
        finally:
            for task in (
                refresh_task,
                communication_loss_task,
                cleaned_consumer_task,
                dlq_consumer_task,
            ):
                task.cancel()
            await cleaned_consumer.stop()
            await dlq_consumer.stop()
            await producer.stop()

if __name__ == "__main__":
    import threading
    from app.health import start_health_server

    # Start health server in background thread
    health_thread = threading.Thread(
        target=start_health_server,
        kwargs={"port": settings.service_port},
        daemon=True,
    )
    health_thread.start()

    service = AnomalyService()
    asyncio.run(service.run())
