import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from config import WebSocketSettings


def test_websocket_config_loads_defaults():
    settings = WebSocketSettings()

    assert settings.service_port == 8004
    assert settings.redis_url == "redis://redis:6379"
    assert settings.fleet_channel == "fleet:live"
    assert settings.eta_channel == "eta:live"


def test_websocket_config_accepts_service_specific_env(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_REDIS_URL", "redis://cache:6379")
    monkeypatch.setenv("WEBSOCKET_FLEET_CHANNEL", "fleet:test")
    monkeypatch.setenv("WEBSOCKET_ETA_CHANNEL", "eta:test")

    settings = WebSocketSettings()

    assert settings.redis_url == "redis://cache:6379"
    assert settings.fleet_channel == "fleet:test"
    assert settings.eta_channel == "eta:test"
