"""Database initialization helpers."""

from sqlalchemy.engine import Engine

from app.core.logging import get_logger
from app.db.base import Base
from app.models import alert, telemetry, user  # noqa: F401 - ensures ORM models register on Base.metadata

logger = get_logger(__name__)


def init_db(target_engine: Engine) -> bool:
    """Create database tables if the database is reachable. Returns True on success."""
    try:
        Base.metadata.create_all(bind=target_engine)
        logger.info("Database schema verified successfully")
        return True
    except Exception as exc:
        logger.warning(
            "Database schema initialization skipped; database unreachable at startup",
            extra={"error": str(exc)},
        )
        return False
