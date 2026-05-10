from app.config import ApiGatewaySettings


def test_api_gateway_config_loads_defaults(monkeypatch):
    # Clear any environment overrides so we test the hardcoded defaults
    monkeypatch.delenv("KEYCLOAK_BASE_URL", raising=False)
    monkeypatch.delenv("KEYCLOAK_REALM", raising=False)
    monkeypatch.delenv("KEYCLOAK_CLIENT_ID", raising=False)
    monkeypatch.delenv("KEYCLOAK_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("KEYCLOAK_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("KEYCLOAK_ADMIN_PASSWORD", raising=False)

    settings = ApiGatewaySettings()

    assert settings.service_port == 8000
    assert settings.route_service_url == "http://route-service:8002"
    assert settings.fleet_service_url == "http://fleet-management-service:8003"
    assert settings.redis_url.startswith("redis://")
    assert settings.keycloak_base_url == "http://keycloak:8080"
    assert settings.keycloak_realm == "ontime"
    assert settings.keycloak_client_id == "ontime-api"


def test_api_gateway_config_prefers_service_specific_env(monkeypatch):
    monkeypatch.setenv("API_GATEWAY_ROUTE_SERVICE_URL", "http://routes.internal:9000")
    monkeypatch.setenv("API_GATEWAY_FLEET_SERVICE_URL", "http://fleet.internal:9001")
    monkeypatch.setenv("API_GATEWAY_REDIS_URL", "redis://cache:6379/2")
    monkeypatch.setenv("API_GATEWAY_KAFKA_PORT", "19092")

    settings = ApiGatewaySettings()

    assert settings.route_service_url == "http://routes.internal:9000"
    assert settings.fleet_service_url == "http://fleet.internal:9001"
    assert settings.redis_url == "redis://cache:6379/2"
    assert settings.kafka_port == 19092
