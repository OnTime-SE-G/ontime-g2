import pytest
from unittest.mock import MagicMock, patch
from app.consumers.crowd_report_consumer import CrowdReportConsumer
from app.database.models import CrowdReport
from fastapi import HTTPException

@patch("app.consumers.crowd_report_consumer.validate_route_stop")
@patch("app.consumers.crowd_report_consumer.adjust_trust_scores")
def test_process_message_success(mock_adjust_trust, mock_validate):
    mock_validate.return_value = None
    db = MagicMock()
    
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
    
    consumer = CrowdReportConsumer()
    consumer._process_message(db, payload)
    
    mock_validate.assert_called_once_with(1, 5)
    db.add.assert_called_once()
    db.commit.assert_called_once()
    mock_adjust_trust.assert_called_once_with(db, 1, 5, 50, "user_123")

@patch("app.consumers.crowd_report_consumer.validate_route_stop")
@patch("app.consumers.crowd_report_consumer.adjust_trust_scores")
def test_process_message_validation_failure(mock_adjust_trust, mock_validate):
    # Simulate a validation exception
    mock_validate.side_effect = HTTPException(status_code=400, detail="Invalid stop ID")
    db = MagicMock()
    
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
    
    consumer = CrowdReportConsumer()
    consumer._process_message(db, payload)
    
    mock_validate.assert_called_once_with(1, 5)
    db.add.assert_not_called()
    db.commit.assert_not_called()
    mock_adjust_trust.assert_not_called()
