from unittest.mock import patch, MagicMock
import pytest

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "auth-service"}

@patch("app.routers.auth.keycloak_manager")
def test_login_success(mock_keycloak, client):
    # Mock successful login response from Keycloak
    mock_keycloak.get_token.return_value = {
        "access_token": "fake_access_token",
        "refresh_token": "fake_refresh_token",
        "expires_in": 3600,
        "refresh_expires_in": 36000
    }
    
    response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpassword"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "fake_access_token"
    assert data["refresh_token"] == "fake_refresh_token"
    mock_keycloak.get_token.assert_called_once_with("testuser", "testpassword")

@patch("app.routers.auth.keycloak_manager")
def test_refresh_token(mock_keycloak, client):
    mock_keycloak.refresh_token.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
        "refresh_expires_in": 36000
    }
    
    response = client.post("/auth/refresh?refresh_token=old_token")
    
    assert response.status_code == 200
    assert response.json()["access_token"] == "new_access_token"

@patch("app.routers.auth.keycloak_manager")
def test_logout(mock_keycloak, client):
    response = client.post("/auth/logout?refresh_token=token_to_kill")
    
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}
    mock_keycloak.logout.assert_called_once_with("token_to_kill")
