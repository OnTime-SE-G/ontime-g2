from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

def before_scenario(context, scenario):
    # Set up mocks
    context.get_producer_patcher = patch("app.api.endpoints.get_kafka_producer")
    context.validate_patcher = patch("app.api.endpoints.validate_route_stop")
    context.predictor_patcher = patch("app.api.endpoints.predictor")
    
    context.mock_get_producer = context.get_producer_patcher.start()
    context.mock_validate = context.validate_patcher.start()
    context.mock_predictor = context.predictor_patcher.start()
    
    # Configure default mock behaviors
    context.mock_producer = MagicMock()
    context.mock_get_producer.return_value = context.mock_producer
    context.mock_validate.return_value = None
    
    # Client setup
    context.client = TestClient(app)

def after_scenario(context, scenario):
    # Stop patchers
    context.get_producer_patcher.stop()
    context.validate_patcher.stop()
    context.predictor_patcher.stop()
