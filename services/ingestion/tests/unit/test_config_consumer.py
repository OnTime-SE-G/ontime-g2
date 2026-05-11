import json
from unittest.mock import MagicMock, patch

import pytest
from kafka.consumer.fetcher import ConsumerRecord

from services.ingestion.app.config_consumer import DeviceConfigConsumer


@pytest.fixture
def mock_callback():
    return MagicMock()


@pytest.fixture
def consumer(mock_callback):
    return DeviceConfigConsumer(publish_config_callback=mock_callback)


def test_process_message_valid_payload(consumer, mock_callback):
    payload = {
        "bus_id": "1",
        "location_interval": 10000,
        "heartbeat_interval": 60000,
        "new_bus_id": "99"
    }
    consumer._process_message(payload)
    mock_callback.assert_called_once_with("1", "I:10000,H:60000,B:99")


def test_process_message_missing_bus_id(consumer, mock_callback):
    payload = {
        "location_interval": 10000
    }
    with patch("services.ingestion.app.config_consumer.logger.error") as mock_logger:
        consumer._process_message(payload)
    mock_callback.assert_not_called()
    mock_logger.assert_called_once_with("Invalid config payload: missing bus_id")


def test_process_message_empty_config(consumer, mock_callback):
    payload = {
        "bus_id": "1"
    }
    with patch("services.ingestion.app.config_consumer.logger.warning") as mock_logger:
        consumer._process_message(payload)
    mock_callback.assert_not_called()
    mock_logger.assert_called_once_with("Empty config payload for bus %s", "1")


def test_process_message_handles_exception(consumer, mock_callback):
    payload = {
        "bus_id": "1",
        "location_interval": 10000
    }
    mock_callback.side_effect = Exception("MQTT error")
    with patch("services.ingestion.app.config_consumer.logger.error") as mock_logger:
        consumer._process_message(payload)
    mock_logger.assert_called_once()
    assert "Failed to process config message" in mock_logger.call_args[0][0]


def test_start_and_stop(consumer):
    with patch("threading.Thread") as mock_thread_class:
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread
        
        consumer.start()
        
        mock_thread_class.assert_called_once_with(target=consumer._run, daemon=True)
        mock_thread.start.assert_called_once()
        assert consumer._thread == mock_thread
        
        mock_kafka = MagicMock()
        consumer.consumer = mock_kafka
        
        consumer.stop()
        
        assert consumer._stop_event.is_set()
        mock_kafka.close.assert_called_once()
        mock_thread.join.assert_called_once()


def test_run_initialization_error(consumer):
    with patch("services.ingestion.app.config_consumer.KafkaConsumer") as mock_kafka:
        mock_kafka.side_effect = Exception("Kafka down")
        with patch("services.ingestion.app.config_consumer.logger.error") as mock_logger:
            consumer._run()
        mock_logger.assert_called_once()
        assert "Failed to connect DeviceConfigConsumer to Kafka" in mock_logger.call_args[0][0]


def test_run_processes_messages(consumer):
    mock_kafka = MagicMock()
    
    # We want poll to return messages once, then stop the loop
    def fake_poll(timeout_ms):
        consumer._stop_event.set()  # Stop loop after first poll
        record = MagicMock()
        record.value = {"bus_id": "1", "location_interval": 10000}
        return {
            "topic": [record]
        }
        
    mock_kafka.poll.side_effect = fake_poll
    
    with patch("services.ingestion.app.config_consumer.KafkaConsumer", return_value=mock_kafka):
        with patch.object(consumer, "_process_message") as mock_process:
            consumer._run()
            
    mock_process.assert_called_once_with({"bus_id": "1", "location_interval": 10000})


def test_run_handles_poll_exception(consumer):
    mock_kafka = MagicMock()
    
    def fake_poll(timeout_ms):
        consumer._stop_event.set()
        raise Exception("Poll error")
        
    mock_kafka.poll.side_effect = fake_poll
    
    with patch("services.ingestion.app.config_consumer.KafkaConsumer", return_value=mock_kafka):
        with patch("services.ingestion.app.config_consumer.logger.error") as mock_logger:
            consumer._run()
            
    mock_logger.assert_called_once()
    assert "Error in DeviceConfigConsumer poll loop" in mock_logger.call_args[0][0]
