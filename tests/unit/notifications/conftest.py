"""Fixtures pytest du service notifications."""

import os

os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcde"
os.environ["JWT_ISSUER"] = "marcheci"
os.environ["JWT_AUDIENCE"] = "marcheci"
os.environ["DATABASE_URL"] = "sqlite:///./notifications_test.db"
os.environ["EVENTS_ENABLED"] = "false"

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

TEST_SECRET = "test-secret-0123456789abcdef0123456789abcde"


def make_admin_token() -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "1",
        "role": "ADMIN",
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iss": "marcheci",
        "aud": "marcheci",
    }
    return pyjwt.encode(payload, TEST_SECRET, algorithm="HS256")


ADMIN = {"Authorization": f"Bearer {make_admin_token()}"}


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def db_session(client):
    from app.database import get_db

    db = next(client.app.dependency_overrides[get_db]())
    try:
        yield db
    finally:
        db.close()
