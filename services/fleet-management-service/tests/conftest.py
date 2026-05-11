# tests/conftest.py
import sys
import os
from pathlib import Path

# Add repo root and service root to sys.path
current_file = Path(__file__).resolve()

# 1. Add Service Root
service_root = current_file.parents[1]
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

# 2. Add Repo Root
try:
    repo_root = current_file.parents[3]
except IndexError:
    repo_root = service_root

if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

os.environ["PYTHONPATH"] = f"{service_root}{os.pathsep}{repo_root}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.db_fleet import FleetBusORM, DriverORM, ScheduleORM, PlannedTripORM, TripIncidentORM

# Use test DB
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///test.db")

if TEST_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
