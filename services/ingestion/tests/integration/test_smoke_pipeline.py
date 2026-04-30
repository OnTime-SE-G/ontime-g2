import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import paho.mqtt.client as mqtt
import pytest
from kafka import KafkaConsumer


pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = Path(__file__).with_name("docker-compose.smoke.yml")
HEALTH_URL = "http://127.0.0.1:18001/health/ready"
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 18884
KAFKA_BOOTSTRAP = "127.0.0.1:19092"
RAW_TOPIC = "transport-telemetry-raw"
DLQ_TOPIC = "transport-telemetry-dlq"


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


def wait_for_readiness(timeout_seconds: int = 180) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "no response"
    while time.time() < deadline:
        try:
            response = httpx.get(HEALTH_URL, timeout=3.0)
            if response.status_code == 200 and response.json()["status"] == "healthy":
                return
            last_error = f"{response.status_code}: {response.text}"
        except httpx.HTTPError as error:
            last_error = str(error)
        time.sleep(2)
    raise AssertionError(f"ingestion service did not become ready within {timeout_seconds}s: {last_error}")


def wait_for_kafka(timeout_seconds: int = 60) -> None:
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
        except Exception as error:  # pragma: no cover - exercised only on transient startup failures
            last_error = str(error)
            time.sleep(2)
        finally:
            if consumer is not None:
                consumer.close()
    raise AssertionError(f"Kafka broker did not become reachable within {timeout_seconds}s: {last_error}")


def publish_smoke_messages(valid_payload: dict, invalid_payload: bytes) -> None:
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    try:
        valid_info = client.publish(
            f"transport/bus/{valid_payload['busId']}/location",
            json.dumps(valid_payload),
            qos=1,
        )
        invalid_info = client.publish(
            "transport/bus/BUS_SMOKE_INVALID/location",
            invalid_payload,
            qos=1,
        )
        valid_info.wait_for_publish()
        invalid_info.wait_for_publish()
    finally:
        client.loop_stop()
        client.disconnect()


def wait_for_message(topic: str, predicate, timeout_seconds: int = 60):
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=1000,
        request_timeout_ms=30000,
        api_version_auto_timeout_ms=5000,
        group_id=f"{topic}-{uuid.uuid4().hex}",
        value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        key_deserializer=lambda key: key.decode("utf-8") if key else None,
    )
    deadline = time.time() + timeout_seconds
    try:
        while time.time() < deadline:
            for _, messages in consumer.poll(timeout_ms=1000).items():
                for message in messages:
                    if predicate(message):
                        return message
        raise AssertionError(f"Timed out waiting for expected message on topic {topic}")
    finally:
        consumer.close()


def collect_logs(project_name: str) -> str:
    result = run_compose(project_name, "logs", "--no-color", check=False)
    return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"


def test_mqtt_to_kafka_smoke_pipeline():
    if not docker_is_available():
        pytest.skip("Docker daemon is not reachable. Start Docker to run ingestion smoke tests.")

    project_name = f"ingestionsmoke{uuid.uuid4().hex[:8]}"
    valid_payload = {
        "busId": f"BUS_SMOKE_{uuid.uuid4().hex[:8].upper()}",
        "tripId": "TRIP_SMOKE_001",
        "lat": 6.9271,
        "lon": 79.8612,
        "speed": 32.5,
        "heading": 145.0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        run_compose(project_name, "up", "-d", "--build")
        wait_for_readiness()
        wait_for_kafka()
        publish_smoke_messages(valid_payload, b"bad_data")

        raw_message = wait_for_message(
            RAW_TOPIC,
            lambda message: message.key == valid_payload["busId"]
            and message.value["busId"] == valid_payload["busId"],
        )
        dlq_message = wait_for_message(
            DLQ_TOPIC,
            lambda message: message.value["original_payload"] == "bad_data"
            and message.value["error_type"] == "JSON_PARSE",
        )

        assert raw_message.value["tripId"] == valid_payload["tripId"]
        assert raw_message.value["lat"] == valid_payload["lat"]
        assert raw_message.value["lon"] == valid_payload["lon"]
        assert dlq_message.value["source"] == "mqtt"
        assert dlq_message.value["source_topic"] == "transport/bus/BUS_SMOKE_INVALID/location"
    except Exception as error:
        logs = collect_logs(project_name)
        raise AssertionError(f"{error}\n\nCompose logs:\n{logs}") from error
    finally:
        run_compose(project_name, "down", "-v", "--remove-orphans", check=False)
