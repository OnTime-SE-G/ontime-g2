import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import RouteSettings


def test_route_config_loads_defaults():
    settings = RouteSettings()

    assert settings.service_port == 8002
    assert "postgresql://" in settings.database_url


def test_route_config_accepts_service_specific_database_url(monkeypatch):
    monkeypatch.setenv("ROUTE_DATABASE_URL", "postgresql://route:secret@db:5432/routes")

    settings = RouteSettings()

    assert settings.database_url == "postgresql://route:secret@db:5432/routes"
