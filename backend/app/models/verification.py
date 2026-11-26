"""ORM models for Phase 8 Verification Wall and Human Operator Approvals."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Recommendation(Base):
    """AI Copilot or simulation recommendation submitted to the Verification Wall."""

    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('COPILOT', 'MANUAL')",
            name="ck_recommendations_source_type",
        ),
        CheckConstraint(
            "latest_verification_status IN ('VERIFIED', 'NEEDS_REVIEW', 'REJECTED')",
            name="ck_recommendations_ver_status",
        ),
        CheckConstraint(
            "latest_decision_status IS NULL OR latest_decision_status IN ('APPROVED', 'REJECTED', 'INVESTIGATION_REQUESTED')",
            name="ck_recommendations_dec_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="COPILOT")
    satellite_id: Mapped[str] = mapped_column(String(32), nullable=False, default="SAT-01", index=True)
    subsystem: Mapped[str] = mapped_column(String(64), nullable=False, default="GENERAL", index=True)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    anomaly_summary: Mapped[str] = mapped_column(Text, nullable=False)
    verified_observations: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    possible_explanations: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    supporting_evidence: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    contradicting_or_missing_evidence: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    recommended_checks: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    uncertainty_and_limitations: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    citations: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    retrieved_evidence: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    verified_context: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="GENERATED")
    ai_claimed_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    linked_alert_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    linked_correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    linked_incident_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        ForeignKey(
            "incidents.incident_id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_recommendations_linked_incident",
        ),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_username: Mapped[str] = mapped_column(String(64), nullable=False)
    latest_verification_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="NEEDS_REVIEW", index=True
    )
    latest_decision_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    verifications: Mapped[List["Verification"]] = relationship(
        "Verification",
        back_populates="recommendation",
        cascade="all, delete-orphan",
        order_by="Verification.id.asc()",
    )
    decisions: Mapped[List["OperatorDecision"]] = relationship(
        "OperatorDecision",
        back_populates="recommendation",
        cascade="all, delete-orphan",
        order_by="OperatorDecision.id.asc()",
    )


class Verification(Base):
    """Immutable deterministic Verification Wall evaluation record."""

    __tablename__ = "verifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('VERIFIED', 'NEEDS_REVIEW', 'REJECTED')",
            name="ck_verifications_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verification_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("recommendations.recommendation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    checks: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    supporting_evidence_refs: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    engine_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="deterministic-wall-v1"
    )
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluated_by_username: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    recommendation: Mapped[Recommendation] = relationship("Recommendation", back_populates="verifications")


class OperatorDecision(Base):
    """Immutable human operator approval, rejection, or investigation request."""

    __tablename__ = "operator_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED', 'INVESTIGATION_REQUESTED')",
            name="ck_operator_decisions_decision",
        ),
        CheckConstraint(
            "verification_status_at_decision IN ('VERIFIED', 'NEEDS_REVIEW', 'REJECTED')",
            name="ck_operator_decisions_ver_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("recommendations.recommendation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verification_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("verifications.verification_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    verification_status_at_decision: Mapped[str] = mapped_column(String(24), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operator_username: Mapped[str] = mapped_column(String(64), nullable=False)
    operator_role: Mapped[str] = mapped_column(String(32), nullable=False)
    command_executed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    linked_incident_id: Mapped[Optional[str]] = mapped_column(
        String(32),
        ForeignKey(
            "incidents.incident_id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_operator_decisions_linked_incident",
        ),
        nullable=True,
        index=True,
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    recommendation: Mapped[Recommendation] = relationship("Recommendation", back_populates="decisions")
