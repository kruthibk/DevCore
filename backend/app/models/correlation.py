"""SQLAlchemy ORM model for persisted alert correlation hypotheses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

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


class Correlation(Base):
    """Stores time-window alert correlations and causal hypotheses."""

    __tablename__ = "correlations"
    __table_args__ = (
        Index("ix_correlations_sat_rule_status", "satellite_id", "rule_code", "status"),
        Index("ix_correlations_updated_at", "updated_at"),
        CheckConstraint(
            "suspected_subsystem IN ('EPS', 'THERMAL', 'ADCS', 'OBC', 'SENSORS')",
            name="ck_correlations_valid_subsystem",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'ACKNOWLEDGED', 'DISMISSED')",
            name="ck_correlations_valid_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    satellite_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    suspected_subsystem: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    grouping_reason: Mapped[str] = mapped_column(Text, nullable=False)
    related_alert_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    supporting_evidence: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    contradicting_evidence: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    confidence_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
        index=True,
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
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
            f"<Correlation id={self.correlation_id!r} subsystem={self.suspected_subsystem!r} "
            f"status={self.status!r} alerts={len(self.related_alert_ids or [])}>"
        )
