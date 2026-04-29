from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from schemas.gps import GPSMessage
from services.ingestion.producer import TelemetryProducer


@patch("services.ingestion.producer.KafkaProducer")
def test_publish_valid(mock_kafka_class):
    # Setup mock
    mock_producer = MagicMock()
    mock_kafka_class.return_value = mock_producer

    # Create producer
    producer = TelemetryProducer()

    # Create valid message
    msg = GPSMessage(
        bus_id="BUS_123",
        trip_id="TRIP_123",
        lat=6.9271,
        lon=79.8612,
        speed=45.5,
        heading=120.0,
        timestamp=datetime.now(timezone.utc)
    )

    # Publish
    producer.publish_valid(msg)

    # Validate
    mock_producer.send.assert_called_once()
    args, kwargs = mock_producer.send.call_args
    
    assert kwargs["topic"] == producer.raw_topic
    assert kwargs["key"] == "BUS_123"
    assert "busId" in kwargs["value"]
    assert kwargs["value"]["busId"] == "BUS_123"


@patch("services.ingestion.producer.KafkaProducer")
def test_publish_to_dlq(mock_kafka_class):
    # Setup mock
    mock_producer = MagicMock()
    mock_kafka_class.return_value = mock_producer

    # Create producer
    producer = TelemetryProducer()

    # Fake bad payload
    bad_bytes = b"not a json string"

    # Publish to DLQ
    producer.publish_to_dlq(
        raw_payload=bad_bytes,
        error_reason="Invalid JSON",
        error_type="JSON_PARSE",
        source_topic="transport/bus/BUS_999/location"
    )

    # Validate
    mock_producer.send.assert_called_once()
    args, kwargs = mock_producer.send.call_args

    assert kwargs["topic"] == producer.dlq_topic
    assert kwargs["key"] is None
    
    envelope = kwargs["value"]
    assert envelope["original_payload"] == "not a json string"
    assert envelope["error_reason"] == "Invalid JSON"
    assert envelope["error_type"] == "JSON_PARSE"
    assert envelope["source"] == "mqtt"
