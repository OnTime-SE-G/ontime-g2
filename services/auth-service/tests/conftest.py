import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pathlib import Path
import sys
import os

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

from app.main import app
from app.database import Base, get_db

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
