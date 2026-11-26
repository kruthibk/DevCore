"""Database initialization helpers."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.logging import get_logger
from app.db.base import Base
from app.models import (  # noqa: F401 - ensures ORM models register on Base.metadata
    alert,
    correlation,
    incident,
    telemetry,
    token_revocation,
    user,
    verification,
)

logger = get_logger(__name__)


def _sync_postgres_schema(target_engine: Engine) -> None:
    """Safely sync additive columns and updated constraints on existing PostgreSQL tables."""
    if target_engine.dialect.name != "postgresql":
        return
    with target_engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
        )
        conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_valid_role"))
        conn.execute(
            text(
                "ALTER TABLE users ADD CONSTRAINT ck_users_valid_role "
                "CHECK (role IN ('ADMIN', 'OPERATOR', 'VIEWER', 'admin', 'operator', 'viewer', 'analyst'))"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS linked_correlation_ids JSON NOT NULL DEFAULT '[]'::json"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS linked_recommendation_id VARCHAR(40)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_incidents_linked_recommendation_id "
                "ON incidents (linked_recommendation_id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS linked_incident_id VARCHAR(32)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_recommendations_linked_incident_id "
                "ON recommendations (linked_incident_id)"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE recommendations DROP CONSTRAINT IF EXISTS ck_recommendations_source_type"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE recommendations ADD CONSTRAINT ck_recommendations_source_type "
                "CHECK (source_type IN ('COPILOT', 'MANUAL'))"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE operator_decisions ADD COLUMN IF NOT EXISTS linked_incident_id VARCHAR(32)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_operator_decisions_linked_incident_id "
                "ON operator_decisions (linked_incident_id)"
            )
        )
        conn.execute(
            text("ALTER TABLE incident_logs DROP CONSTRAINT IF EXISTS ck_incident_logs_action")
        )
        conn.execute(
            text(
                "ALTER TABLE incident_logs ADD CONSTRAINT ck_incident_logs_action "
                "CHECK (action IN ('CREATED', 'STATUS_CHANGE', 'NOTE_ADDED', 'RECOMMENDATION_LINKED', 'VERIFICATION_RECORDED', 'DECISION_RECORDED'))"
            )
        )


def init_db(target_engine: Engine) -> bool:
    """Create database tables and sync additive PostgreSQL schema changes if reachable."""
    try:
        Base.metadata.create_all(bind=target_engine)
        _sync_postgres_schema(target_engine)
        logger.info("Database schema verified successfully")
        return True
    except Exception as exc:
        logger.warning(
            "Database schema initialization skipped; database unreachable at startup",
            extra={"error": str(exc)},
        )
        return False
