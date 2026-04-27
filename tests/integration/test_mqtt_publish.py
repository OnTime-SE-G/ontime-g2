# tests/integration/test_mqtt_publish.py

import json
import socket
import time

import paho.mqtt.client as mqtt
import pytest

from scripts.gps_simulator import create_status_message


BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC = "transport/bus/999/location"


def mqtt_is_reachable() -> bool:
    try:
        with socket.create_connection(
            (BROKER_HOST, BROKER_PORT),
            timeout=2
        ):
            return True
    except OSError:
        return False


@pytest.mark.integration
def test_mqtt_message_is_received():
    if not mqtt_is_reachable():
        pytest.skip(
            "MQTT broker is not reachable. Start the mqtt service with docker compose."
        )

    received = []

    def on_message(client, userdata, msg):
        payload = json.loads(msg.payload.decode("utf-8"))
        received.append(
            {
                "topic": msg.topic,
                "payload": payload,
            }
        )

    subscriber = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    subscriber.on_message = on_message
    subscriber.connect(BROKER_HOST, BROKER_PORT, 60)
    subscriber.subscribe(TOPIC)
    subscriber.loop_start()

    time.sleep(0.5)

    publisher = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    publisher.connect(BROKER_HOST, BROKER_PORT, 60)

    payload = create_status_message(
        bus_id=999,
        route_id=1,
        status="STARTED"
    )

    publisher.publish(
        TOPIC,
        json.dumps(payload),
        qos=1
    )

    timeout = time.time() + 5

    while not received and time.time() < timeout:
        time.sleep(0.1)

    subscriber.loop_stop()
    subscriber.disconnect()
    publisher.disconnect()

    assert len(received) == 1
    assert received[0]["topic"] == TOPIC
    assert received[0]["payload"]["busId"] == 999
    assert received[0]["payload"]["routeId"] == 1
    assert received[0]["payload"]["status"] == "STARTED"
    assert received[0]["payload"]["type"] == "STATUS"
