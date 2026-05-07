from unittest.mock import patch
import pytest

@patch("app.routers.users.keycloak_manager")
def test_register_user(mock_keycloak, client):
    # Mock Keycloak user creation
    mock_keycloak.create_user.return_value = "fake-keycloak-uuid"
    
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "securepassword",
        "first_name": "Test",
        "last_name": "User"
    }
    
    response = client.post("/users/register", json=user_data)
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "fake-keycloak-uuid"
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    
    # Verify it was also saved in the DB (via GET)
    response_get = client.get(f"/users/fake-keycloak-uuid")
    assert response_get.status_code == 200
    assert response_get.json()["email"] == "test@example.com"

def test_get_user_not_found(client):
    response = client.get("/users/non-existent-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_get_me_not_implemented(client):
    response = client.get("/users/me")
    assert response.status_code == 501
