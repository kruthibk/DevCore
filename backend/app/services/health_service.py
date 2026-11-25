"""Health check service functions for backend and PostgreSQL connectivity."""

from datetime import datetime, timezone
from time import perf_counter

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.health import DatabaseHealthResponse, HealthResponse

logger = get_logger(__name__)

APP_START_MONOTONIC = perf_counter()


def get_service_health(settings: Settings) -> HealthResponse:
    """Build the service-level health payload."""
    uptime = round(perf_counter() - APP_START_MONOTONIC, 3)
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc),
    )


def check_database_health(db: Session) -> tuple[DatabaseHealthResponse, bool]:
    """Verify database connectivity with a lightweight SELECT 1 probe.

    Returns (payload, is_healthy) and handles database failures gracefully.
    """
    dialect = db.bind.dialect.name if db.bind is not None else "unknown"
    started = perf_counter()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return (
            DatabaseHealthResponse(
                status="healthy",
                database="connected",
                dialect=dialect,
                latency_ms=latency_ms,
                timestamp=datetime.now(timezone.utc),
            ),
            True,
        )
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000, 2)
        logger.error(
            "Database health check failed",
            extra={"dialect": dialect, "latency_ms": latency_ms, "error": str(exc)},
        )
        return (
            DatabaseHealthResponse(
                status="unhealthy",
                database="disconnected",
                dialect=dialect,
                latency_ms=latency_ms,
                error="Database connection failed or timed out.",
                timestamp=datetime.now(timezone.utc),
            ),
            False,
        )
