"""SQLAlchemy ORM model for persisted anomaly and sensor integrity alerts."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Alert(Base):
    """Stores deduplicated anomaly and sensor integrity alerts."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_sat_sensor_type_status", "satellite_id", "sensor_name", "alert_type", "status"),
        Index("ix_alerts_last_detected_at", "last_detected_at"),
        CheckConstraint(
            "alert_type IN ('STATISTICAL_ANOMALY', 'RATE_OF_CHANGE', 'ENGINEERING_LIMIT', "
            "'SENSOR_MISSING', 'SENSOR_FROZEN', 'SENSOR_INVALID', 'SENSOR_STALE')",
            name="ck_alerts_valid_type",
        ),
        CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'CRITICAL')",
            name="ck_alerts_valid_severity",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'ACKNOWLEDGED', 'RESOLVED')",
            name="ck_alerts_valid_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    satellite_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sensor_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    observed_value: Mapped[Optional[float]] = mapped_column(
        Numeric(14, 4, asdecimal=False),
        nullable=True,
    )
    expected_range: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    z_score: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 4, asdecimal=False),
        nullable=True,
    )
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<Alert alert_id={self.alert_id!r} type={self.alert_type!r} "
            f"severity={self.severity!r} status={self.status!r}>"
        )
