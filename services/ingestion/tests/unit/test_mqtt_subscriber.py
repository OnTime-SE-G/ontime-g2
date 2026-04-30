from unittest.mock import MagicMock

import pytest

import services.ingestion.app.mqtt_subscriber as subscriber_module
from services.ingestion.app.metrics import MetricsCollector
from services.ingestion.app.validator import ValidationResult


@pytest.fixture
def subscriber_with_mocks(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(subscriber_module.mqtt, "Client", MagicMock(return_value=mock_client))
    collector = MetricsCollector()
    monkeypatch.setattr(subscriber_module, "metrics", collector)
    mock_producer = MagicMock()
    subscriber = subscriber_module.MQTTSubscriber(producer=mock_producer)
    return subscriber, mock_producer, mock_client, collector


def test_init_requires_producer():
    with pytest.raises(ValueError, match="TelemetryProducer is required"):
        subscriber_module.MQTTSubscriber(producer=None)


def test_connect_uses_configured_broker(subscriber_with_mocks):
    subscriber, _, mock_client, _ = subscriber_with_mocks
    subscriber.connect()
    mock_client.connect.assert_called_once_with(
        subscriber_module.settings.mqtt_broker_host,
        subscriber_module.settings.mqtt_broker_port,
        60,
    )


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

    mock_client.subscribe.assert_called_once_with(subscriber_module.settings.mqtt_topic_pattern)
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
    payload = (
        b'{"busId": "BUS_001", "tripId": "TRIP_001", "lat": 6.9271, '
        b'"lon": 79.8612, "speed": 45.0, "heading": 120.0}'
    )

    mock_msg = MagicMock()
    mock_msg.topic = "transport/bus/BUS_001/location"
    mock_msg.payload = payload

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert subscriber.messages_received == 1
    assert subscriber.messages_validated == 1
    assert subscriber.messages_rejected == 0
    assert collector.get_snapshot()["messages_validated"] == 1
    mock_producer.publish_valid.assert_called_once()
    mock_producer.publish_to_dlq.assert_not_called()


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
    mock_msg = MagicMock(topic="transport/bus/BUS_404/location", payload=b"bad")

    subscriber.on_message(client=None, userdata=None, msg=mock_msg)

    assert subscriber.messages_rejected == 1
    assert collector.get_snapshot()["messages_rejected"] == 0
    mock_producer.publish_to_dlq.assert_called_once_with(
        raw_payload=b"bad",
        error_reason="Unknown Error",
        error_type="UNKNOWN",
        source_topic="transport/bus/BUS_404/location",
    )
