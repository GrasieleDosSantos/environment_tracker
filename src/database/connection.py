from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _enable_sqlite_wal(dbapi_conn: object, connection_record: object) -> None:
    """Enable WAL mode and set a generous busy timeout for SQLite.

    WAL allows concurrent reads alongside a single writer.  The busy_timeout
    tells SQLite to retry for up to 30 s before raising 'database is locked',
    which prevents contention errors when multiple background threads write
    cache entries simultaneously (dashboard, trends, map parallel loaders).
    """
    cursor = getattr(dbapi_conn, "cursor", None)
    if cursor:
        c = dbapi_conn.cursor()  # type: ignore[union-attr]
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")  # 30 s — covers worst-case parallel writes
        c.execute("PRAGMA foreign_keys=ON")
        c.close()


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    settings = get_settings()
    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 30},
            echo=False,
        )
        event.listen(_engine, "connect", _enable_sqlite_wal)
    else:
        # PostgreSQL — use connection pooling
        _engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )

    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager that yields a database session and handles commit/rollback."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
