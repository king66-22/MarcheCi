"""Connexion SQLAlchemy (pattern 2.x). Pool sain pour uWSGI/uvicorn workers."""

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
    engine_kwargs["pool_size"] = settings.db_pool_size
    engine_kwargs["max_overflow"] = settings.db_max_overflow
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(settings.database_url, **engine_kwargs)

if _is_sqlite:
    # Active les contraintes FK sous SQLite (postgreSQL : natif)
    @event.listens_for(engine, "connect")
    def _fk_pragma(dbapi_connection, _):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """Dépendance FastAPI : une session par requête."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
