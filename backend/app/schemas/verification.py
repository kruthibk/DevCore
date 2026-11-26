"""Pydantic schemas for Phase 8 Verification Wall and Human Operator Approvals."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

VerificationStatus = Literal["VERIFIED", "NEEDS_REVIEW", "REJECTED"]
CheckStatus = Literal["PASS", "WARN", "FAIL"]
DecisionAction = Literal["APPROVED", "REJECTED", "INVESTIGATION_REQUESTED"]
SourceType = Literal["COPILOT", "MANUAL"]


class VerificationCheckResult(BaseModel):
    """Outcome of a single deterministic Verification Wall rule."""

    rule_id: str
    name: str
    status: CheckStatus
    detail: str


class VerificationEvaluateRequest(BaseModel):
    """Payload submitted to evaluate an AI or simulator recommendation."""

    recommendation_id: Optional[str] = Field(default=None, max_length=40)
    source_type: SourceType = "COPILOT"
    satellite_id: str = Field(default="SAT-01", max_length=32)
    subsystem: str = Field(default="GENERAL", max_length=64)
    question: Optional[str] = Field(default=None, max_length=2000)
    anomaly_summary: str = Field(..., min_length=3, max_length=4000)
    verified_observations: List[str] = Field(default_factory=list)
    possible_explanations: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_or_missing_evidence: List[str] = Field(default_factory=list)
    recommended_checks: List[str] = Field(default_factory=list)
    uncertainty_and_limitations: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    verified_context: Dict[str, Any] = Field(default_factory=dict)
    generation_status: str = Field(default="GENERATED", max_length=32)
    ai_claimed_status: Optional[str] = Field(default=None, max_length=32)
    linked_alert_id: Optional[str] = Field(default=None, max_length=64)
    linked_correlation_id: Optional[str] = Field(default=None, max_length=64)
    linked_incident_id: Optional[str] = Field(default=None, max_length=32)


class VerificationRead(BaseModel):
    """Persisted Verification Wall evaluation result."""

    model_config = ConfigDict(from_attributes=True)

    verification_id: str
    recommendation_id: str
    status: VerificationStatus
    checks: List[VerificationCheckResult]
    supporting_evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    engine_version: str
    disclaimer: str
    evaluated_by_username: str
    verified_at: datetime


class OperatorDecisionRead(BaseModel):
    """Persisted human operator decision record (never triggers commands)."""

    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    recommendation_id: str
    verification_id: str
    verification_status_at_decision: VerificationStatus
    decision: DecisionAction
    reason: Optional[str] = None
    notes: Optional[str] = None
    operator_username: str
    operator_role: str
    command_executed: bool = False
    linked_incident_id: Optional[str] = None
    decided_at: datetime


class RecommendationRead(BaseModel):
    """Summary view of a submitted recommendation."""

    model_config = ConfigDict(from_attributes=True)

    recommendation_id: str
    source_type: SourceType
    satellite_id: str
    subsystem: str
    question: Optional[str] = None
    anomaly_summary: str
    verified_observations: List[str] = Field(default_factory=list)
    possible_explanations: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_or_missing_evidence: List[str] = Field(default_factory=list)
    recommended_checks: List[str] = Field(default_factory=list)
    uncertainty_and_limitations: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    verified_context: Dict[str, Any] = Field(default_factory=dict)
    generation_status: str
    ai_claimed_status: Optional[str] = None
    linked_alert_id: Optional[str] = None
    linked_correlation_id: Optional[str] = None
    linked_incident_id: Optional[str] = None
    created_by_username: str
    latest_verification_status: VerificationStatus
    latest_decision_status: Optional[DecisionAction] = None
    created_at: datetime
    updated_at: datetime


class RecommendationDetail(RecommendationRead):
    """Full recommendation record with historical verifications and human decisions."""

    verifications: List[VerificationRead] = Field(default_factory=list)
    decisions: List[OperatorDecisionRead] = Field(default_factory=list)
    latest_verification: Optional[VerificationRead] = None
    latest_decision: Optional[OperatorDecisionRead] = None


class RecommendationListResponse(BaseModel):
    """Paginated list of recommendations for the Verification Wall."""

    total: int
    summary: Dict[str, int]
    items: List[RecommendationRead]


class DecisionApproveRequest(BaseModel):
    """Operator approval request (never executes spacecraft commands)."""

    notes: Optional[str] = Field(default=None, max_length=2000)
    incident_id: Optional[str] = Field(default=None, max_length=32)


class DecisionReasonRequest(BaseModel):
    """Operator rejection or investigation request requiring an explicit reason."""

    reason: str = Field(..., min_length=5, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=2000)
    incident_id: Optional[str] = Field(default=None, max_length=32)


class DecisionHistoryItem(OperatorDecisionRead):
    """Operator decision joined with recommendation context for audit history."""

    recommendation_summary: Optional[str] = None
    subsystem: Optional[str] = None


class DecisionHistoryResponse(BaseModel):
    """Paginated chronological human operator decision log."""

    total: int
    items: List[DecisionHistoryItem]
