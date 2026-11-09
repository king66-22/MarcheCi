"""Fixtures pytest du service utilisateurs : SQLite mémoire, fakeredis pour le rate-limit."""

import os

os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcde"
os.environ["JWT_ISSUER"] = "marcheci"
os.environ["JWT_AUDIENCE"] = "marcheci"
os.environ["REDIS_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///./utilisateurs_test.db"

import pytest
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.security import RateLimiter, set_rate_limiter_for_tests


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
    set_rate_limiter_for_tests(RateLimiter("redis://x", 5, 300, enabled=False))

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def rate_limited():
    """Active le rate-limit avec fakeredis."""
    rl = RateLimiter("redis://x", 5, 300, enabled=False)
    rl._redis = FakeStrictRedis(decode_responses=True)
    set_rate_limiter_for_tests(rl)
    yield rl
    set_rate_limiter_for_tests(RateLimiter("redis://x", 5, 300, enabled=False))


def create_user_api(client: TestClient, email: str, password: str = "MotDePasse123", role: str | None = None):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    if role == "ADMIN" and resp.status_code == 201:
        # Passe la BDD en direct pour promouvoir en ADMIN (les ADMIN ne naissent jamais côté API publique)
        from app.database import get_db

        db = next(client.app.dependency_overrides[get_db]())
        from app.models import User

        user = db.scalar(__import__("sqlalchemy", fromlist=["select"]).select(User).where(User.email == email))
        user.role = "ADMIN"
        db.commit()
    return resp
