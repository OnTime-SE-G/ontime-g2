from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from schemas.gps import GPSMessage
from services.ingestion.app.producer import TelemetryProducer


@patch("services.ingestion.app.producer.KafkaProducer")
def test_publish_valid(mock_kafka_class):
    mock_producer = MagicMock()
    mock_kafka_class.return_value = mock_producer

    producer = TelemetryProducer()
    mock_kafka_class.assert_called_once()

    msg = GPSMessage(
        bus_id="BUS_123",
        trip_id="TRIP_123",
        lat=6.9271,
        lon=79.8612,
        speed=45.5,
        heading=120.0,
        timestamp=datetime.now(timezone.utc),
    )

    producer.publish_valid(msg)

    mock_producer.send.assert_called_once()
    _, kwargs = mock_producer.send.call_args
    assert kwargs["topic"] == producer.raw_topic
    assert kwargs["key"] == "BUS_123"
    assert "busId" in kwargs["value"]
    assert kwargs["value"]["busId"] == "BUS_123"
    assert isinstance(kwargs["value"]["timestamp"], str)


@patch("services.ingestion.app.producer.KafkaProducer")
def test_publish_to_dlq(mock_kafka_class):
    mock_producer = MagicMock()
    mock_kafka_class.return_value = mock_producer

    producer = TelemetryProducer()

    bad_bytes = b"not a json string"

    producer.publish_to_dlq(
        raw_payload=bad_bytes,
        error_reason="Invalid JSON",
        error_type="JSON_PARSE",
        source_topic="transport/bus/BUS_999/location",
    )

    mock_producer.send.assert_called_once()
    _, kwargs = mock_producer.send.call_args

    assert kwargs["topic"] == producer.dlq_topic
    assert kwargs["key"] is None
    envelope = kwargs["value"]
    assert envelope["original_payload"] == "not a json string"
    assert envelope["error_reason"] == "Invalid JSON"
    assert envelope["error_type"] == "JSON_PARSE"
    assert envelope["source"] == "mqtt"


@patch("services.ingestion.app.producer.KafkaProducer")
def test_close_flushes_and_closes(mock_kafka_class):
    mock_producer = MagicMock()
    mock_kafka_class.return_value = mock_producer

    producer = TelemetryProducer()
    producer.close()

    mock_producer.flush.assert_called_once_with()
    mock_producer.close.assert_called_once_with()
