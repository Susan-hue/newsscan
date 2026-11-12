"""Database engine and session handling (synchronous SQLAlchemy)."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from newsscan.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_sessionmaker: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _sessionmaker
    if _engine is None:
        url = get_settings().database_url
        kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(url, **kwargs)
        _sessionmaker = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Drop the cached engine. Used by tests that point the app at a fresh database."""
    global _engine, _sessionmaker
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    get_engine()
    assert _sessionmaker is not None
    with _sessionmaker() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session for code outside a request, such as the worker."""
    get_engine()
    assert _sessionmaker is not None
    with _sessionmaker() as session:
        yield session
