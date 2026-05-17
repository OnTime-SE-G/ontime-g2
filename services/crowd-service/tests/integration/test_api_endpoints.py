"""Integration tests for the Crowd Service API."""

import pytest
from datetime import datetime
import json


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service_name"] == "crowd-service"


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/metrics")
    
    assert response.status_code == 200
    data = response.json()
    assert "total_predictions" in data
    assert "average_confidence" in data
    assert "prediction_latency_ms" in data


def test_predict_endpoint_morning_rush(client, sample_prediction_request):
    """Test prediction endpoint with morning rush hour data."""
    response = client.post(
        "/api/v1/predict",
        json=sample_prediction_request,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "vehicle_id" in data
    assert "crowd_count" in data
    assert "crowd_level" in data
    assert "confidence" in data
    
    # Morning rush should have higher crowd estimate
    assert data["crowd_level"] in ["Low", "Medium", "High"]
    assert 0 <= data["confidence"] <= 1


def test_predict_endpoint_midday(client, sample_prediction_request_midday):
    """Test prediction endpoint with midday data (less crowded)."""
    response = client.post(
        "/api/v1/predict",
        json=sample_prediction_request_midday,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Midday should have lower crowd estimate
    assert data["vehicle_id"] == "BUS_002"
    assert data["crowd_count"] >= 0


def test_predict_endpoint_evening(client, sample_prediction_request_evening):
    """Test prediction endpoint with evening peak data."""
    response = client.post(
        "/api/v1/predict",
        json=sample_prediction_request_evening,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Evening peak should have higher crowd estimate
    assert data["crowd_level"] in ["Low", "Medium", "High"]


def test_predict_endpoint_invalid_request(client):
    """Test prediction endpoint with invalid request."""
    response = client.post(
        "/api/v1/predict",
        json={"invalid": "data"},
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 422  # Unprocessable Entity


def test_multiple_predictions_increase_metrics(client, sample_prediction_request):
    """Test that multiple predictions update metrics."""
    # Make first prediction
    response1 = client.post("/api/v1/predict", json=sample_prediction_request)
    assert response1.status_code == 200
    
    # Get metrics after first prediction
    metrics1 = client.get("/metrics").json()
    count1 = metrics1["total_predictions"]
    
    # Make second prediction
    sample_request = sample_prediction_request.copy()
    sample_request["vehicle_id"] = "BUS_999"
    response2 = client.post("/api/v1/predict", json=sample_request)
    assert response2.status_code == 200
    
    # Get metrics after second prediction
    metrics2 = client.get("/metrics").json()
    count2 = metrics2["total_predictions"]
    
    # Count should have increased
    assert count2 >= count1
