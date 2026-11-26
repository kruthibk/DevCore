"""ORM models for Incident Registry and immutable Audit Trail logs."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Incident(Base):
    """Tracked operational anomaly incident."""

    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("severity IN ('CRITICAL', 'WARNING', 'INFO')", name="ck_incidents_severity"),
        CheckConstraint(
            "status IN ('OPEN', 'INVESTIGATING', 'MITIGATED', 'CLOSED')",
            name="ck_incidents_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    subsystem: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERAL", server_default="GENERAL")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="WARNING", server_default="WARNING")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN", server_default="OPEN")
    linked_alert_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    linked_correlation_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    linked_recommendation_id: Mapped[Optional[str]] = mapped_column(
        String(40),
        ForeignKey(
            "recommendations.recommendation_id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_incidents_linked_recommendation",
        ),
        nullable=True,
        index=True,
    )
    copilot_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
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

    logs: Mapped[List["IncidentLog"]] = relationship(
        "IncidentLog",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentLog.id.asc()",
    )


class IncidentLog(Base):
    """Immutable chronological audit log entry for an incident."""

    __tablename__ = "incident_logs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('CREATED', 'STATUS_CHANGE', 'NOTE_ADDED', 'RECOMMENDATION_LINKED', 'VERIFICATION_RECORDED', 'DECISION_RECORDED')",
            name="ck_incident_logs_action",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("incidents.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    incident: Mapped[Incident] = relationship("Incident", back_populates="logs")
