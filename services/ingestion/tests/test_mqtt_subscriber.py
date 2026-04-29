from unittest.mock import MagicMock

from services.ingestion.mqtt_subscriber import MQTTSubscriber


def test_on_message_valid_payload():
    # Setup
    mock_producer = MagicMock()
    subscriber = MQTTSubscriber(producer=mock_producer)
    
    # Valid JSON payload matching GPSMessage requirements
    payload = b'{"busId": "BUS_001", "tripId": "TRIP_001", "lat": 6.9271, "lon": 79.8612, "speed": 45.0, "heading": 120.0}'
    
    mock_msg = MagicMock()
    mock_msg.topic = "transport/bus/BUS_001/location"
    mock_msg.payload = payload
    
    # Act
    subscriber.on_message(client=None, userdata=None, msg=mock_msg)
    
    # Assert
    assert subscriber.messages_received == 1
    assert subscriber.messages_validated == 1
    assert subscriber.messages_rejected == 0
    mock_producer.publish_valid.assert_called_once()
    mock_producer.publish_to_dlq.assert_not_called()


def test_on_message_invalid_payload():
    # Setup
    mock_producer = MagicMock()
    subscriber = MQTTSubscriber(producer=mock_producer)
    
    # Invalid JSON payload
    payload = b'bad_data'
    
    mock_msg = MagicMock()
    mock_msg.topic = "transport/bus/BUS_001/location"
    mock_msg.payload = payload
    
    # Act
    subscriber.on_message(client=None, userdata=None, msg=mock_msg)
    
    # Assert
    assert subscriber.messages_received == 1
    assert subscriber.messages_validated == 0
    assert subscriber.messages_rejected == 1
    mock_producer.publish_valid.assert_not_called()
    mock_producer.publish_to_dlq.assert_called_once()
