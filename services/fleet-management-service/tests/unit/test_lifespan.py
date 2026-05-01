import asyncio

import pytest
from fastapi import FastAPI

from app.main import lifespan


def test_lifespan_creates_database_tables(monkeypatch):
    calls = []

    def create_all(bind):
        calls.append(bind)

    monkeypatch.setattr("app.main.Base.metadata.create_all", create_all)

    async def run_lifespan():
        async with lifespan(FastAPI()):
            pass

    asyncio.run(run_lifespan())

    assert len(calls) == 1


def test_lifespan_raises_when_database_is_unavailable(monkeypatch):
    def create_all(bind):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.main.Base.metadata.create_all", create_all)
    monkeypatch.setattr("app.main.time.sleep", lambda seconds: None)

    async def run_lifespan():
        async with lifespan(FastAPI()):
            pass

    with pytest.raises(RuntimeError, match="Database not available"):
        asyncio.run(run_lifespan())
