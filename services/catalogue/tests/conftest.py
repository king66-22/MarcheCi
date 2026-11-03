"""Fixtures pytest du catalogue : app FastAPI en mémoire (SQLite + fakeredis)."""

import os

os.environ["JWT_SECRET"] = "test-secret"
os.environ["JWT_ISSUER"] = "marcheci"
os.environ["JWT_AUDIENCE"] = "marcheci"
os.environ["REDIS_ENABLED"] = "false"  # activé précisément par la fixture « cache »
os.environ["DATABASE_URL"] = "sqlite:///./catalogue_test.db"

import pytest
from fakeredis import FakeStrictRedis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cache import get_product_cache
from app.config import get_settings
from app.database import Base, get_db
from app.deps import get_current_payload
from app.main import app


@pytest.fixture()
def client():
    """Client FastAPI sans BDD réseau : SQLite en mémoire + cache désactivé."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    disabled_cache = get_product_cache()
    disabled_cache.enabled = False
    disabled_cache._client = None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_product_cache] = lambda: disabled_cache

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def admin_auth():
    """Simule un JWT ADMIN validé (bypass de la dépendance d'authentification)."""
    app.dependency_overrides[get_current_payload] = lambda: {
        "sub": "1",
        "role": "ADMIN",
        "exp": 4102444800,
    }
    yield
    app.dependency_overrides.pop(get_current_payload, None)


@pytest.fixture()
def client_auth(client, admin_auth):
    yield client


@pytest.fixture()
def cache(client):
    """Active le cache avec fakeredis (pour tester TTL et invalidation)."""
    fake = FakeStrictRedis(decode_responses=True)
    from app.cache import ProductCache

    live = ProductCache(url="redis://localhost", ttl_seconds=get_settings().products_cache_ttl_seconds, enabled=False)
    live._client = fake
    client.app.dependency_overrides[get_product_cache] = lambda: live
    yield fake
    client.app.dependency_overrides.pop(get_product_cache, None)


def make_jwt(payload: dict, secret: str = "test-secret") -> str:
    import jwt as pyjwt

    return pyjwt.encode(payload, secret, algorithm="HS256", issuer="marcheci", audience="marcheci")
