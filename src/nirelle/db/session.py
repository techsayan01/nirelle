"""Engine/session setup.

Defaults to a local SQLite file, matching the BRD's MVP isolation model
(single shared database, row-level tenant filtering) chosen for build
speed for one pilot school. Swap `database_url` for a Postgres DSN later
without touching the models or repository layer.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, StaticPool, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DATABASE_URL = "sqlite:///nirelle.db"


def create_db_engine(database_url: str = DEFAULT_DATABASE_URL, *, echo: bool = False) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    # An in-memory SQLite DB lives only on its one connection; without
    # StaticPool, each new connection (i.e. each session) would see a
    # fresh, empty database instead of the same one.
    is_in_memory = is_sqlite and ":memory:" in database_url
    kwargs = {"poolclass": StaticPool} if is_in_memory else {}
    engine = create_engine(database_url, echo=echo, connect_args=connect_args, **kwargs)

    if is_sqlite:
        # SQLite ignores FOREIGN KEY constraints unless told otherwise per
        # connection - without this, the composite (school_id, student_id)
        # foreign keys that enforce tenant isolation at the schema level
        # (see models.py) would silently do nothing.
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """Create all tables. Fine for MVP/pilot scale; swap for a real
    migration tool (e.g. Alembic) once the schema needs to evolve under
    live data.
    """
    Base.metadata.create_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope: commits on success, rolls back and
    re-raises on error.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
