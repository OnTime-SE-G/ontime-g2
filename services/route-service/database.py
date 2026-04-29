import os

from sqlalchemy import create_engine


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/ontime_db"
)


def get_engine():
    return create_engine(DATABASE_URL, echo=False)