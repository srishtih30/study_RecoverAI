"""
Test configuration.

Sets DATABASE_URL (and other required env vars) to a throwaway SQLite file
BEFORE any `app.*` module is imported, so app.config.get_settings() picks up
the test database rather than requiring a running Postgres instance. This is
what lets `pytest` run without docker-compose / Postgres / Redis running —
see README.md "Testing".
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = BACKEND_ROOT / "test_recoverai.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")
os.environ.setdefault("BACKEND_CORS_ORIGINS", "http://localhost:5173")

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    from app.db.session import engine
    from app.models import Base

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except PermissionError:
            pass



@pytest.fixture()
def db_session() -> Session:
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
