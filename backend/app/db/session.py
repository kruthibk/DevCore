"""SQLAlchemy engine and session lifecycle management."""

from collections.abc import Generator
from typing import Any, Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(database_url: str | None = None, connect_timeout: int | None = None) -> Engine:
    """Create a configured SQLAlchemy engine."""
    settings = get_settings()
    url = database_url or settings.database_url
    timeout = connect_timeout if connect_timeout is not None else settings.db_connect_timeout

    connect_args: Dict[str, Any] = {}
    if url.startswith("postgresql"):
        connect_args["connect_timeout"] = timeout

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


engine = build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
