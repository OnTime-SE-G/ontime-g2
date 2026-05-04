import json
import subprocess
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest

mqtt = pytest.importorskip("paho.mqtt.client")
redis_module = pytest.importorskip("redis")
websocket_module = pytest.importorskip("websocket")
kafka_module = pytest.importorskip("kafka")
KafkaConsumer = kafka_module.KafkaConsumer


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = Path(__file__).with_name("docker-compose.live-pipeline.yml")

KAFKA_BOOTSTRAP = "127.0.0.1:19093"
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 18885
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 16380

ROUTE_URL = "http://127.0.0.1:18012"
FLEET_URL = "http://127.0.0.1:18013"
INGESTION_URL = "http://127.0.0.1:18011"
WEBSOCKET_URL = "ws://127.0.0.1:18014/v1/live"

TRIP_LIFECYCLE_TOPIC = "trip.lifecycle"
RAW_TOPIC = "transport-telemetry-raw"
CLEANED_TOPIC = "transport-telemetry-cleaned"

SMOKE_KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Smoke Route Path</name>
      <LineString>
        <coordinates>
          79.8612,6.9271,0 79.8620,6.9280,0 79.8630,6.9290,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Smoke Start Stop</name>
      <Point><coordinates>79.8612,6.9271,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Smoke End Stop</name>
      <Point><coordinates>79.8630,6.9290,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def docker_is_available() -> bool:
    result = subprocess.run(
        ["docker", "version"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def run_compose(project_name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    command = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "-p",
        project_name,
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"docker compose failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def collect_logs(project_name: str) -> str:
    result = run_compose(project_name, "logs", "--no-color", check=False)
    return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def wait_for_http_json(url: str, predicate, timeout_seconds: int = 180) -> dict:
    deadline = time.time() + timeout_seconds
    last_error = "no response"
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=5.0)
            last_error = f"{response.status_code}: {response.text}"
            if response.status_code < 500:
                payload = response.json()
                if predicate(payload):
                    return payload
        except Exception as error:  # pragma: no cover - startup timing only
            last_error = str(error)
        time.sleep(2)
    raise AssertionError(f"Timed out waiting for {url}: {last_error}")


def wait_for_kafka(timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "broker not ready"
    while time.time() < deadline:
        consumer = None
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                request_timeout_ms=5000,
                api_version_auto_timeout_ms=5000,
            )
            consumer.topics()
            return
        except Exception as error:  # pragma: no cover - startup timing only
            last_error = str(error)
            time.sleep(2)
        finally:
            if consumer is not None:
                consumer.close()
    raise AssertionError(f"Kafka did not become reachable: {last_error}")


def wait_for_message(topic: str, predicate, timeout_seconds: int = 120):
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=1000,
        request_timeout_ms=30000,
        api_version_auto_timeout_ms=5000,
        group_id=f"live-pipeline-smoke-{topic}-{uuid.uuid4().hex}",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        key_deserializer=lambda key: key.decode("utf-8") if key else None,
    )
    deadline = time.time() + timeout_seconds
    seen_messages = []
    try:
        while time.time() < deadline:
            for _, messages in consumer.poll(timeout_ms=1000).items():
                for message in messages:
                    seen_messages.append(
                        {
                            "key": message.key,
                            "value": message.value,
                        }
                    )
                    seen_messages = seen_messages[-5:]
                    if predicate(message):
                        return message
        raise AssertionError(
            f"Timed out waiting for expected message on {topic}; "
            f"last seen messages={seen_messages}"
        )
    finally:
        consumer.close()


def upload_smoke_route(route_name: str) -> int:
    response = httpx.post(
        f"{ROUTE_URL}/api/v1/admin/routes/add-route",
        data={"route_name": route_name},
        files={"file": ("smoke-route.kml", SMOKE_KML, "application/vnd.google-earth.kml+xml")},
        timeout=30.0,
    )
    response.raise_for_status()
    return int(response.json()["route_id"])


def create_and_start_trip(route_id: int, unique_suffix: str) -> tuple[str, str]:
    bus_response = httpx.post(
        f"{FLEET_URL}/api/v1/fleet/buses",
        json={
            "fleet_code": f"BUS-{unique_suffix}",
            "plate_number": f"WP-{unique_suffix}",
            "capacity": 48,
        },
        timeout=30.0,
    )
    bus_response.raise_for_status()
    bus_id = str(bus_response.json()["id"])

    driver_response = httpx.post(
        f"{FLEET_URL}/api/v1/fleet/drivers",
        json={
            "name": f"Smoke Driver {unique_suffix}",
            "license_number": f"LIC-{unique_suffix}",
            "phone": "0770000000",
        },
        timeout=30.0,
    )
    driver_response.raise_for_status()
    driver_id = int(driver_response.json()["id"])

    today = date.today()
    schedule_response = httpx.post(
        f"{FLEET_URL}/api/v1/fleet/schedules",
        json={
            "route_id": route_id,
            "scheduled_time": "10:00:00",
            "day_of_week": today.weekday(),
        },
        timeout=30.0,
    )
    schedule_response.raise_for_status()

    generate_response = httpx.post(
        f"{FLEET_URL}/api/v1/fleet/planned-trips/generate",
        params={"target_date": today.isoformat()},
        timeout=30.0,
    )
    generate_response.raise_for_status()

    trips_response = httpx.get(f"{FLEET_URL}/api/v1/fleet/planned-trips/today", timeout=30.0)
    trips_response.raise_for_status()
    trips = trips_response.json()
    assert trips, "Fleet did not generate a planned trip for today"

    trip_id = str(trips[0]["id"])
    assign_response = httpx.patch(
        f"{FLEET_URL}/api/v1/fleet/planned-trips/{trip_id}/assign",
        params={"bus_id": bus_id, "driver_id": driver_id},
        timeout=30.0,
    )
    assign_response.raise_for_status()

    start_response = httpx.post(
        f"{FLEET_URL}/api/v1/fleet/planned-trips/{trip_id}/start",
        timeout=30.0,
    )
    start_response.raise_for_status()
    assert start_response.json()["status"] == "EN_ROUTE"
    return bus_id, trip_id


def wait_for_ingestion_active_trip(timeout_seconds: int = 60) -> None:
    wait_for_http_json(
        f"{INGESTION_URL}/health",
        lambda payload: payload["dependencies"]["trip_cache"] == "ready"
        and payload["counters"]["active_trip_count"] >= 1,
        timeout_seconds=timeout_seconds,
    )


def wait_for_flink_job_running(timeout_seconds: int = 180) -> None:
    wait_for_http_json(
        "http://127.0.0.1:18081/jobs",
        lambda payload: any(job.get("status") == "RUNNING" for job in payload.get("jobs", [])),
        timeout_seconds=timeout_seconds,
    )


def make_gps_payload(bus_id: str) -> dict:
    return {
        "busId": bus_id,
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 32.5,
        "heading": 145.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def publish_mqtt_gps(payload: dict) -> None:
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    try:
        info = client.publish(
            f"transport/bus/{payload['busId']}/location",
            json.dumps(payload),
            qos=1,
            retain=False,
        )
        info.wait_for_publish()
        assert info.rc == mqtt.MQTT_ERR_SUCCESS
    finally:
        client.loop_stop()
        client.disconnect()


def wait_for_cleaned_message_with_republish(bus_id: str, trip_id: str, route_id: int, timeout_seconds: int = 240):
    consumer = KafkaConsumer(
        CLEANED_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=1000,
        request_timeout_ms=30000,
        api_version_auto_timeout_ms=5000,
        group_id=f"live-pipeline-smoke-cleaned-{uuid.uuid4().hex}",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        key_deserializer=lambda key: key.decode("utf-8") if key else None,
    )
    deadline = time.time() + timeout_seconds
    next_publish_at = 0.0
    seen_messages = []

    try:
        while time.time() < deadline:
            now = time.time()
            if now >= next_publish_at:
                publish_mqtt_gps(make_gps_payload(bus_id))
                next_publish_at = now + 2.0

            for _, messages in consumer.poll(timeout_ms=1000).items():
                for message in messages:
                    seen_messages.append(
                        {
                            "key": message.key,
                            "value": message.value,
                        }
                    )
                    seen_messages = seen_messages[-5:]
                    if (
                        message.value.get("busId") == bus_id
                        and message.value.get("tripId") == trip_id
                        and message.value.get("routeId") == str(route_id)
                    ):
                        return message

        raise AssertionError(
            "Timed out waiting for cleaned enriched telemetry; "
            f"last seen messages={seen_messages}"
        )
    finally:
        consumer.close()


def wait_for_redis_position(bus_id: str, trip_id: str, timeout_seconds: int = 90) -> dict:
    client = redis_module.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    key = f"bus:{bus_id}:position"
    deadline = time.time() + timeout_seconds
    last_value = None
    while time.time() < deadline:
        last_value = client.get(key)
        if last_value:
            payload = json.loads(last_value)
            if payload.get("busId") == bus_id and payload.get("tripId") == trip_id:
                return payload
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for Redis key {key}; last value={last_value}")


def wait_for_websocket_snapshot(bus_id: str, trip_id: str, timeout_seconds: int = 60) -> dict:
    deadline = time.time() + timeout_seconds
    last_error = "no websocket message"
    while time.time() < deadline:
        ws = None
        try:
            ws = websocket_module.create_connection(
                f"{WEBSOCKET_URL}?busId={bus_id}",
                timeout=5,
            )
            payload = json.loads(ws.recv())
            if payload.get("busId") == bus_id and payload.get("tripId") == trip_id:
                return payload
            last_error = f"unexpected payload: {payload}"
        except Exception as error:  # pragma: no cover - startup timing only
            last_error = str(error)
            time.sleep(1)
        finally:
            if ws is not None:
                ws.close()
    raise AssertionError(f"Timed out waiting for websocket snapshot: {last_error}")


def test_fleet_mqtt_ingestion_flink_redis_websocket_smoke():
    if not docker_is_available():
        pytest.skip("Docker daemon is not reachable. Start Docker to run the live pipeline smoke test.")

    project_name = f"livepipesmoke{uuid.uuid4().hex[:8]}"
    unique_suffix = uuid.uuid4().hex[:8].upper()

    try:
        run_compose(project_name, "up", "-d", "--build")
        wait_for_kafka()
        wait_for_http_json(f"{ROUTE_URL}/health", lambda payload: payload["status"] == "ok")
        wait_for_http_json(f"{FLEET_URL}/health/ready", lambda payload: payload["status"] == "ready")
        wait_for_http_json(f"{INGESTION_URL}/health/ready", lambda payload: payload["status"] == "healthy")
        wait_for_http_json("http://127.0.0.1:18014/health/ready", lambda payload: payload["status"] == "ready")
        wait_for_flink_job_running()

        route_id = upload_smoke_route(f"Smoke Route {unique_suffix}")
        bus_id, trip_id = create_and_start_trip(route_id, unique_suffix)

        lifecycle_message = wait_for_message(
            TRIP_LIFECYCLE_TOPIC,
            lambda message: message.value.get("event") == "TRIP_STARTED"
            and message.value.get("busId") == bus_id
            and message.value.get("tripId") == trip_id,
            timeout_seconds=60,
        )
        assert lifecycle_message.value["routeId"] == str(route_id)

        wait_for_ingestion_active_trip()

        gps_payload = make_gps_payload(bus_id)
        publish_mqtt_gps(gps_payload)

        raw_message = wait_for_message(
            RAW_TOPIC,
            lambda message: message.key == bus_id
            and message.value.get("busId") == bus_id
            and message.value.get("tripId") == trip_id,
            timeout_seconds=60,
        )
        assert raw_message.value["lat"] == gps_payload["lat"]
        assert raw_message.value["lon"] == gps_payload["lon"]

        cleaned_message = wait_for_cleaned_message_with_republish(bus_id, trip_id, route_id)
        assert "routeProgressPct" in cleaned_message.value
        assert "remainingDistanceToNextStops" in cleaned_message.value

        redis_payload = wait_for_redis_position(bus_id, trip_id)
        assert redis_payload["routeId"] == str(route_id)

        websocket_payload = wait_for_websocket_snapshot(bus_id, trip_id)
        assert websocket_payload["routeId"] == str(route_id)
    except Exception as error:
        logs = collect_logs(project_name)
        raise AssertionError(f"{error}\n\nCompose logs:\n{logs}") from error
    finally:
        run_compose(project_name, "down", "-v", "--remove-orphans", check=False)
