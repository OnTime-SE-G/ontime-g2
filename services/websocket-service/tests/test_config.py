import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from config import WebSocketSettings


def test_websocket_config_loads_defaults(monkeypatch):
    monkeypatch.delenv("WEBSOCKET_SERVICE_PORT", raising=False)
    monkeypatch.delenv("SERVICE_PORT", raising=False)
    monkeypatch.delenv("WEBSOCKET_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("WEBSOCKET_FLEET_CHANNEL", raising=False)
    monkeypatch.delenv("FLEET_CHANNEL", raising=False)
    monkeypatch.delenv("WEBSOCKET_ETA_CHANNEL", raising=False)
    monkeypatch.delenv("ETA_CHANNEL", raising=False)
    monkeypatch.delenv("WEBSOCKET_ANOMALY_CHANNEL", raising=False)
    monkeypatch.delenv("ANOMALY_CHANNEL", raising=False)

    settings = WebSocketSettings()

    assert settings.service_port == 8004
    assert settings.redis_url == "redis://redis:6379"
    assert settings.fleet_channel == "fleet:live"
    assert settings.eta_channel == "eta:live"
    assert settings.anomaly_channel == "anomaly:live"


def test_websocket_config_accepts_service_specific_env(monkeypatch):
    monkeypatch.setenv("WEBSOCKET_REDIS_URL", "redis://cache:6379")
    monkeypatch.setenv("WEBSOCKET_FLEET_CHANNEL", "fleet:test")
    monkeypatch.setenv("WEBSOCKET_ETA_CHANNEL", "eta:test")
    monkeypatch.setenv("WEBSOCKET_ANOMALY_CHANNEL", "anomaly:test")

    settings = WebSocketSettings()

    assert settings.redis_url == "redis://cache:6379"
    assert settings.fleet_channel == "fleet:test"
    assert settings.eta_channel == "eta:test"
    assert settings.anomaly_channel == "anomaly:test"
