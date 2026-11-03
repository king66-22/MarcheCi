"""Connexion SQLAlchemy — pattern commun des quatre services."""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()
_is_sqlite = settings.database_url.startswith("sqlite")

engine_kwargs: dict = {"echo": False, "future": True}
if _is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(pool_size=settings.db_pool_size, pool_pre_ping=True)

engine = create_engine(settings.database_url, **engine_kwargs)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> SessionLocal:  # type: ignore[return-value]
    """Point d'injection utilisé par le consommateur (monkeypatchable en tests)."""
    return SessionLocal()
