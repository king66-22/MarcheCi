"""Fixtures pytest du service commandes : SQLite mémoire + catalogue factice + producteur factice."""

import os

os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcde"
os.environ["JWT_ISSUER"] = "marcheci"
os.environ["JWT_AUDIENCE"] = "marcheci"
os.environ["DATABASE_URL"] = "sqlite:///./commandes_test.db"
os.environ["EVENTS_ENABLED"] = "false"

import time
from datetime import UTC, datetime, timedelta

import pytest
import jwt as pyjwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import services as svc
from app.catalogue_client import CatalogueProduct
from app.database import Base, get_db
from app.events import OrderEventPublisher
from app.service_auth import ServiceAuth
from app.main import app

TEST_SECRET = "test-secret-0123456789abcdef0123456789abcde"


def make_token(user_id: int, role: str = "CLIENT") -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iss": "marcheci",
        "aud": "marcheci",
    }
    return pyjwt.encode(payload, TEST_SECRET, algorithm="HS256")


class FakeCatalogue:
    """Catalogue in-memory contrôlable dans les tests."""

    def __init__(self):
        self.products: dict[int, CatalogueProduct] = {}
        self.unavailable = False

    def set(self, pid: int, name: str, price: int, stock: int, active: bool = True, behaviour: str = "ok"):
        p_ = dict(id=pid, name=name, price_xof=price, stock=stock, is_active=active)
        self.products[pid] = p_
        return self

    def fetch_products(self, ids):
        if self.unavailable:
            raise svc.CatalogueUnavailable("catalogue down")
        out = []
        for pid in sorted(set(ids)):
            d = self.products.get(pid)
            if d is None:
                continue
            out.append(
                CatalogueProduct(
                    id=d["id"], name=d["name"], price_xof=d["price_xof"],
                    stock=d["stock"], is_active=d["is_active"],
                )
            )
        return out

    def adjust_stock(self, pid, delta, token):
        if self.unavailable:
            raise svc.CatalogueUnavailable("catalogue down during stock decrement")
        p = self.products[pid]
        if p["stock"] + delta < 0:
            return False
        p["stock"] = p["stock"] + delta
        return True


class FakePublisher:
    """Producteur d'événements factice : enregistre les publications."""

    def __init__(self):
        self.published: list[dict] = []
        self.fail = False

    def publish_order_created(self, event: dict) -> bool:
        if self.fail:
            return False
        self.published.append(event)
        return True


class FakeServiceAuth:
    def get_token(self) -> str:
        return "fake-sys-token"


@pytest.fixture()
def fake_catalogue_data(fake_catalogue):
    """Appelle la fixture catalogue."""
    return fake_catalogue


@pytest.fixture()
def catalogue_ok(fake_catalogue):
    return fake_catalogue


@pytest.fixture()
def fake_catalogue():
    c = FakeCatalogue()
    return c


@pytest.fixture()
def fake_publisher():
    return FakePublisher()


@pytest.fixture()
def client(fake_catalogue, fake_publisher):
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
    svc.set_catalogue_client_for_tests(fake_catalogue)
    svc.set_publisher_for_tests(fake_publisher)
    svc.set_service_auth_for_tests(FakeServiceAuth())

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
