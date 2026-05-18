"""Shared fixtures for ETA integration tests."""

import pytest


@pytest.fixture(autouse=True)
def skip_eta_db_writes(monkeypatch):
    """Avoid Postgres connection attempts in CI (eta_db is optional at test time)."""
    monkeypatch.setattr("app.consumers.eta_consumer.insert_eta_record", lambda *args, **kwargs: None)
