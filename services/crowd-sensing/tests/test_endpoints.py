import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@patch("app.api.endpoints.producer")
def test_submit_crowd_report_success(mock_producer):
    mock_producer.send = MagicMock()
    
    payload = {
        "trip_id": "TRIP_123",
        "route_id": 1,
        "direction_id": 0,
        "stop_id": 5,
        "stop_sequence": 1,
        "occupancy_score": 50,
        "timestamp": "2026-05-17T20:00:00"
    }
    
    response = client.post("/api/v1/crowd/report", json=payload)
    
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    mock_producer.send.assert_called_once()

@patch("app.api.endpoints.producer")
def test_submit_crowd_report_with_passenger_id(mock_producer):
    mock_producer.send = MagicMock()
    
    payload = {
        "trip_id": "TRIP_123",
        "route_id": 1,
        "direction_id": 0,
        "stop_id": 5,
        "stop_sequence": 1,
        "occupancy_score": 50,
        "passenger_id": "user_123",
        "timestamp": "2026-05-17T20:00:00"
    }
    
    response = client.post("/api/v1/crowd/report", json=payload)
    
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    mock_producer.send.assert_called_once()
    # Verify passenger_id was included in the dictionary sent to producer
    args, kwargs = mock_producer.send.call_args
    sent_dict = args[1]
    assert sent_dict["passenger_id"] == "user_123"

def test_submit_crowd_report_invalid_score():
    payload = {
        "trip_id": "TRIP_123",
        "route_id": 1,
        "direction_id": 0,
        "stop_id": 5,
        "stop_sequence": 1,
        "occupancy_score": 150,  # Invalid (> 100)
        "timestamp": "2026-05-17T20:00:00"
    }
    
    response = client.post("/api/v1/crowd/report", json=payload)
    # Pydantic validation handles this ge/le constraint
    assert response.status_code == 422

@patch("app.api.endpoints.producer", None)
def test_submit_crowd_report_broker_unavailable():
    payload = {
        "trip_id": "TRIP_123",
        "route_id": 1,
        "direction_id": 0,
        "stop_id": 5,
        "stop_sequence": 1,
        "occupancy_score": 50,
        "timestamp": "2026-05-17T20:00:00"
    }
    
    response = client.post("/api/v1/crowd/report", json=payload)
    
    assert response.status_code == 503
    assert "Message broker unavailable" in response.json()["detail"]

@patch("app.api.endpoints.validate_route_stop")
@patch("app.api.endpoints.predictor")
def test_get_crowd_prediction_success(mock_predictor, mock_validate):
    mock_validate.return_value = None
    mock_predictor.predict.return_value = {
        "prediction": "SEMI_FULL",
        "confidence": 0.85,
        "historical_prediction": "NOT_FULL",
        "live_adjustment": True,
        "live_report_count": 3,
        "source": "hybrid_prediction"
    }
    
    response = client.get("/api/v1/crowd/predict?route_id=1&stop_id=5&direction_id=0&datetime=2026-05-17T20:00:00Z")
    
    assert response.status_code == 200
    data = response.json()
    assert data["prediction"] == "SEMI_FULL"
    assert data["confidence"] == 0.85
    assert data["live_adjustment"] is True
    assert data["live_report_count"] == 3
    mock_validate.assert_called_once_with(1, 5)

@patch("app.api.endpoints.validate_route_stop")
def test_get_crowd_prediction_invalid_datetime(mock_validate):
    mock_validate.return_value = None
    response = client.get("/api/v1/crowd/predict?route_id=1&stop_id=5&direction_id=0&datetime=invalid-date-format")
    
    assert response.status_code == 400
    assert "Invalid datetime format" in response.json()["detail"]

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

