import pytest
from unittest.mock import patch, MagicMock
from app.utils.validation import validate_route_stop
from fastapi import HTTPException

@patch("urllib.request.urlopen")
def test_validate_route_stop_success(mock_urlopen):
    # Mocking central route service endpoint with associated stops
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"stops": [{"id": 5}, {"id": 10}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    # Should succeed without raising any validation exceptions
    validate_route_stop(route_id=1, stop_id=5)

@patch("urllib.request.urlopen")
def test_validate_route_stop_failure(mock_urlopen):
    # Mocking response where the requested stop does not belong to the route
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"stops": [{"id": 10}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    # Should fail with 400 Bad Request exception
    with pytest.raises(HTTPException) as exc_info:
        validate_route_stop(route_id=1, stop_id=5)
    
    assert exc_info.value.status_code == 400
    assert "is not associated with Route ID" in exc_info.value.detail
