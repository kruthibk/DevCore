"""Schemas for service and database health responses."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response model for GET /health."""

    status: Literal["healthy", "degraded"]
    service: str
    version: str
    environment: str
    uptime_seconds: float
    timestamp: datetime


class DatabaseHealthResponse(BaseModel):
    """Response model for GET /health/db."""

    status: Literal["healthy", "unhealthy"]
    database: Literal["connected", "disconnected"]
    dialect: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime
