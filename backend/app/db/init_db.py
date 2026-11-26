"""Database initialization helpers and idempotent demo user seeding."""

from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.base import Base
from app.models import alert, correlation, incident, telemetry, user  # noqa: F401 - ensures ORM models register on Base.metadata
from app.models.user import User

logger = get_logger(__name__)

DEMO_USERS = (
    ("admin", "admin@devcore.space", "AdminPass!2026", "ADMIN"),
    ("operator", "operator@devcore.space", "OperatorPass!2026", "OPERATOR"),
    ("viewer", "viewer@devcore.space", "ViewerPass!2026", "VIEWER"),
)


def _sync_postgres_users_schema(target_engine: Engine) -> None:
    """Safely add is_active column and update role constraint on existing PostgreSQL users table."""
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


def seed_demo_users(db: Session) -> int:
    """Idempotently seed demo ADMIN, OPERATOR, and VIEWER accounts if missing."""
    created = 0
    for username, email, raw_password, role in DEMO_USERS:
        existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            User(
                username=username,
                email=email,
                password_hash=hash_password(raw_password),
                role=role,
                is_active=True,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def init_db(target_engine: Engine) -> bool:
    """Create database tables, sync legacy columns, and seed demo users if reachable."""
    try:
        Base.metadata.create_all(bind=target_engine)
        _sync_postgres_users_schema(target_engine)
        with Session(bind=target_engine) as db:
            seeded = seed_demo_users(db)
            if seeded:
                logger.info("Seeded demo RBAC users", extra={"seeded_count": seeded})
        logger.info("Database schema verified successfully")
        return True
    except Exception as exc:
        logger.warning(
            "Database schema initialization skipped; database unreachable at startup",
            extra={"error": str(exc)},
        )
        return False
