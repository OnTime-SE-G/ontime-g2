import json
from collections import deque
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import services.ingestion.app.mqtt_subscriber as subscriber_module
import services.ingestion.app.trip_lifecycle_cache as cache_module
from services.ingestion.app.metrics import MetricsCollector
from services.ingestion.app.trip_lifecycle_cache import ActiveTripCache, decode_trip_lifecycle_event
from services.ingestion.app.validator import ValidationResult


@pytest.fixture
def subscriber_with_mocks(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(subscriber_module.mqtt, "Client", MagicMock(return_value=mock_client))
    collector = MetricsCollector()
    monkeypatch.setattr(subscriber_module, "metrics", collector)
    monkeypatch.setattr(cache_module, "metrics", collector)
    trip_cache = ActiveTripCache()
    trip_cache.apply_event(
        decode_trip_lifecycle_event(
            {
                "event": "TRIP_STARTED",
                "busId": "1",
                "tripId": "TRIP_001",
                "routeId": "202",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
    )
    mock_producer = MagicMock()
    subscriber = subscriber_module.MQTTSubscriber(producer=mock_producer, trip_cache=trip_cache)
    return subscriber, mock_producer, mock_client, collector


def test_init_requires_producer():
    with pytest.raises(ValueError, match="TelemetryProducer is required"):
        subscriber_module.MQTTSubscriber(producer=None)


def test_connect_uses_configured_broker(subscriber_with_mocks, monkeypatch):
    subscriber, _, mock_client, _ = subscriber_with_mocks
    
    # Ensure settings are at defaults regardless of .env content
    monkeypatch.setattr(subscriber_module.settings, "mqtt_username", None)
    monkeypatch.setattr(subscriber_module.settings, "mqtt_password", None)
    monkeypatch.setattr(subscriber_module.settings, "mqtt_tls_enabled", False)
    monkeypatch.setattr(subscriber_module.settings, "mqtt_broker_host", "mqtt-broker")
    monkeypatch.setattr(subscriber_module.settings, "mqtt_broker_port", 1883)

    subscriber.connect()
    mock_client.connect.assert_called_once_with(
        "mqtt-broker",
        1883,
        60,
    )
    mock_client.username_pw_set.assert_not_called()
    mock_client.tls_set.assert_not_called()


def test_connect_configures_username_password_when_present(subscriber_with_mocks, monkeypatch):
    subscriber, _, mock_client, _ = subscriber_with_mocks
    monkeypatch.setattr(subscriber_module.settings, "mqtt_username", "device-user")
    monkeypatch.setattr(subscriber_module.settings, "mqtt_password", "device-pass")

    subscriber.connect()

    mock_client.username_pw_set.assert_called_once_with("device-user", "device-pass")
    mock_client.connect.assert_called_once()


def test_connect_configures_tls_when_enabled(subscriber_with_mocks, monkeypatch):
    subscriber, _, mock_client, _ = subscriber_with_mocks
    monkeypatch.setattr(subscriber_module.settings, "mqtt_tls_enabled", True)
    monkeypatch.setattr(subscriber_module.settings, "mqtt_ca_cert_path", None)

    subscriber.connect()

    mock_client.tls_set.assert_called_once_with()
    mock_client.connect.assert_called_once()


def test_connect_configures_tls_with_ca_cert_path(subscriber_with_mocks, monkeypatch):
    subscriber, _, mock_client, _ = subscriber_with_mocks
    monkeypatch.setattr(subscriber_module.settings, "mqtt_tls_enabled", True)
    monkeypatch.setattr(subscriber_module.settings, "mqtt_ca_cert_path", "/certs/ca.pem")

    subscriber.connect()

    mock_client.tls_set.assert_called_once_with(ca_certs="/certs/ca.pem")
    mock_client.connect.assert_called_once()


def test_start_uses_loop_forever(subscriber_with_mocks):
    subscriber, _, mock_client, _ = subscriber_with_mocks
    subscriber.start()
    mock_client.loop_forever.assert_called_once_with()


def test_stop_stops_loop_and_disconnects(subscriber_with_mocks):
    subscriber, _, mock_client, _ = subscriber_with_mocks
    subscriber.stop()
    mock_client.loop_stop.assert_called_once_with()
    mock_client.disconnect.assert_called_once_with()


def test_on_connect_success_subscribes_and_marks_broker_up(subscriber_with_mocks):
    subscriber, _, mock_client, collector = subscriber_with_mocks

    subscriber.on_connect(
        client=mock_client,
        userdata=None,
        connect_flags=None,
        reason_code=0,
        properties=None,
    )

    mock_client.subscribe.assert_called_once_with(
        [
            (subscriber_module.settings.mqtt_topic_pattern, 0),
            (subscriber_module.settings.mqtt_heartbeat_topic_pattern, 0),
        ]
    )
    assert collector.mqtt_broker_up is True


def test_on_connect_failure_marks_broker_down(subscriber_with_mocks):
    subscriber, _, mock_client, collector = subscriber_with_mocks

    subscriber.on_connect(
        client=mock_client,
        userdata=None,
        connect_flags=None,
        reason_code=5,
        properties=None,
    )

    mock_client.subscribe.assert_not_called()
    assert collector.mqtt_broker_up is False


def test_on_disconnect_marks_broker_down(subscriber_with_mocks):
    subscriber, _, _, collector = subscriber_with_mocks
    collector.mqtt_broker_up = True

    subscriber.on_disconnect(
        client=None,
        userdata=None,
        disconnect_flags=None,
        reason_code=1,
        properties=None,
    )

    assert collector.mqtt_broker_up is False


def test_on_disconnect_clean_shutdown_marks_broker_down(subscriber_with_mocks):
    subscriber, _, _, collector = subscriber_with_mocks
    collector.mqtt_broker_up = True

    subscriber.on_disconnect(
        client=None,
        userdata=None,
        disconnect_flags=None,
        reason_code=0,
        properties=None,
    )

    assert collector.mqtt_broker_up is False


def test_on_message_valid_payload(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks
    payload = json.dumps(
        {
            "busId": "1",
            "lat": 6.9271,
            "lon": 79.8612,
            "speed": 45.0,
            "heading": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")

    mock_msg = MagicMock()
    mock_msg.topic = "transport/bus/1/location"
    mock_msg.payload = payload

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert subscriber.messages_received == 1
    assert subscriber.messages_validated == 1
    assert subscriber.messages_rejected == 0
    assert collector.get_snapshot()["messages_validated"] == 1
    mock_producer.publish_valid.assert_called_once()
    published_message = mock_producer.publish_valid.call_args.args[0]
    assert published_message.bus_id == "1"
    assert published_message.trip_id == "TRIP_001"
    mock_producer.publish_to_dlq.assert_not_called()


def test_on_message_valid_heartbeat_tracks_device_status_only(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks
    payload = json.dumps(
        {
            "busId": "1",
            "deviceId": "GPS-1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gpsFix": True,
            "satellites": 8,
            "signalQuality": 21,
            "batteryVoltage": 3.9,
            "firmwareVersion": "g1-0.1.0",
        }
    ).encode("utf-8")
    mock_msg = MagicMock(topic="transport/bus/1/heartbeat", payload=payload)

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    snapshot = collector.get_snapshot()
    assert snapshot["messages_received"] == 1
    assert snapshot["heartbeat_messages_received"] == 1
    assert snapshot["heartbeat_messages_invalid"] == 0
    assert "1" in snapshot["latest_heartbeat_by_bus"]
    assert subscriber.messages_validated == 0
    assert subscriber.messages_rejected == 0
    mock_producer.publish_valid.assert_not_called()
    mock_producer.publish_to_dlq.assert_not_called()


def test_invalid_heartbeat_does_not_affect_location_validation(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks
    heartbeat_msg = MagicMock(
        topic="transport/bus/1/heartbeat",
        payload=b"bad_data",
    )
    location_payload = json.dumps(
        {
            "busId": "1",
            "lat": 6.9271,
            "lon": 79.8612,
            "speed": 45.0,
            "heading": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    location_msg = MagicMock(topic="transport/bus/1/location", payload=location_payload)

    subscriber.on_message(client=None, userdata=None, msg=heartbeat_msg)
    subscriber.on_message(client=None, userdata=None, msg=location_msg)

    snapshot = collector.get_snapshot()
    assert snapshot["messages_received"] == 2
    assert snapshot["heartbeat_messages_invalid"] == 1
    assert subscriber.messages_validated == 1
    assert subscriber.messages_rejected == 0
    mock_producer.publish_valid.assert_called_once()
    mock_producer.publish_to_dlq.assert_not_called()


def test_on_message_inactive_trip_goes_to_dlq(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks
    payload = json.dumps(
        {
            "busId": "404",
            "lat": 6.9271,
            "lon": 79.8612,
            "speed": 45.0,
            "heading": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    mock_msg = MagicMock(topic="transport/bus/404/location", payload=payload)

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert subscriber.messages_rejected == 1
    assert collector.get_snapshot()["messages_rejected_inactive_trip"] == 1
    mock_producer.publish_valid.assert_not_called()
    mock_producer.publish_to_dlq.assert_called_once()
    _, kwargs = mock_producer.publish_to_dlq.call_args
    assert kwargs["error_type"] == "INACTIVE_TRIP"


def test_on_message_invalid_payload(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks

    mock_msg = MagicMock()
    mock_msg.topic = "transport/bus/BUS_001/location"
    mock_msg.payload = b"bad_data"

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert subscriber.messages_received == 1
    assert subscriber.messages_validated == 0
    assert subscriber.messages_rejected == 1
    assert collector.get_snapshot()["messages_rejected_json"] == 1
    mock_producer.publish_valid.assert_not_called()
    mock_producer.publish_to_dlq.assert_called_once()


def test_on_message_uses_unknown_dlq_fallbacks(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks
    subscriber.validator = MagicMock(
        validate=MagicMock(
            return_value=ValidationResult(
                success=False,
                error_reason=None,
                error_type=None,
            )
        )
    )
    payload = json.dumps(
        {
            "busId": "1",
            "lat": 6.9271,
            "lon": 79.8612,
            "speed": 45.0,
            "heading": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    mock_msg = MagicMock(topic="transport/bus/1/location", payload=payload)

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert subscriber.messages_rejected == 1
    assert collector.get_snapshot()["messages_rejected"] == 0
    mock_producer.publish_to_dlq.assert_called_once_with(
        raw_payload=payload,
        error_reason="Unknown Error",
        error_type="UNKNOWN",
        source_topic="transport/bus/1/location",
    )


def test_rebuilding_trip_cache_buffers_startup_message(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks
    subscriber.trip_cache.mark_rebuilding()
    payload = json.dumps(
        {
            "busId": "1",
            "lat": 6.9271,
            "lon": 79.8612,
            "speed": 45.0,
            "heading": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    mock_msg = MagicMock(topic="transport/bus/1/location", payload=payload)

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert len(subscriber.startup_buffer) == 1
    assert subscriber.messages_validated == 0
    assert subscriber.messages_rejected == 0
    assert collector.get_snapshot()["messages_received"] == 1
    mock_producer.publish_valid.assert_not_called()

    subscriber.trip_cache.mark_ready()
    subscriber.drain_startup_buffer()

    assert len(subscriber.startup_buffer) == 0
    assert subscriber.messages_validated == 1
    mock_producer.publish_valid.assert_called_once()


def test_full_startup_buffer_rejects_with_trip_cache_rebuilding(subscriber_with_mocks):
    subscriber, mock_producer, _, collector = subscriber_with_mocks
    subscriber.trip_cache.mark_rebuilding()
    subscriber.startup_buffer = deque([(b"older", "transport/bus/1/location")], maxlen=1)
    payload = json.dumps(
        {
            "busId": "1",
            "lat": 6.9271,
            "lon": 79.8612,
            "speed": 45.0,
            "heading": 120.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")
    mock_msg = MagicMock(topic="transport/bus/1/location", payload=payload)

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert subscriber.messages_rejected == 1
    assert collector.get_snapshot()["messages_rejected_trip_cache_rebuilding"] == 1
    mock_producer.publish_valid.assert_not_called()
    mock_producer.publish_to_dlq.assert_called_once()
    _, kwargs = mock_producer.publish_to_dlq.call_args
    assert kwargs["error_type"] == "TRIP_CACHE_REBUILDING"


def test_stateless_mode_forwards_physics_violations_to_flink(monkeypatch):
    collector = MetricsCollector()
    monkeypatch.setattr(subscriber_module, "metrics", collector)
    monkeypatch.setattr(subscriber_module.settings, "stateless_mode", True)
    mock_producer = MagicMock()
    subscriber = subscriber_module.MQTTSubscriber(producer=mock_producer, trip_cache=None)

    payload = json.dumps(
        {
            "busId": "B1",
            "lat": 0.0,
            "lon": 0.0,
            "speed": 260.0,
            "timestamp": "2026-05-02T10:00:00Z",
        }
    ).encode("utf-8")

    subscriber._process_payload(payload, "transport/bus/B1/location")

    mock_producer.publish_raw_bytes.assert_called_once_with(payload, "transport/bus/B1/location")
    mock_producer.publish_to_dlq.assert_not_called()
