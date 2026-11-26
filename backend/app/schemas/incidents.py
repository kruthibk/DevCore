"""Pydantic schemas for Incident Registry and Audit Trail APIs."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.alerts import AlertRead
from app.schemas.fault_graph import CorrelationRead
from app.schemas.verification import RecommendationDetail

IncidentSeverity = Literal["CRITICAL", "WARNING", "INFO"]
IncidentStatus = Literal["OPEN", "INVESTIGATING", "MITIGATED", "CLOSED"]
IncidentAction = Literal[
    "CREATED",
    "STATUS_CHANGE",
    "NOTE_ADDED",
    "RECOMMENDATION_LINKED",
    "VERIFICATION_RECORDED",
    "DECISION_RECORDED",
]


class IncidentCreate(BaseModel):
    """Request payload for creating an incident manually or from alerts/Copilot."""

    title: str = Field(..., min_length=3, max_length=200)
    summary: str = Field(..., min_length=3, max_length=4000)
    subsystem: str = Field(default="GENERAL", max_length=64)
    severity: IncidentSeverity = "WARNING"
    linked_alert_ids: List[str] = Field(default_factory=list)
    linked_correlation_ids: List[str] = Field(default_factory=list)
    linked_recommendation_id: Optional[str] = Field(default=None, max_length=40)
    copilot_summary: Optional[str] = Field(default=None, max_length=6000)
    assigned_to: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=2000)


class IncidentUpdate(BaseModel):
    """Request payload for transitioning incident status or assignee."""

    status: Optional[IncidentStatus] = None
    assigned_to: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=2000)


class IncidentLogCreate(BaseModel):
    """Request payload for appending an investigation note."""

    note: str = Field(..., min_length=2, max_length=2000)


class IncidentLogRead(BaseModel):
    """Chronological immutable audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: str
    actor: str
    role: str
    action: IncidentAction
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    note: str
    created_at: datetime


class IncidentSummaryCounts(BaseModel):
    """Aggregate incident counters by workflow status."""

    total: int
    open: int
    investigating: int
    mitigated: int
    closed: int
    resolved: int


class IncidentRead(BaseModel):
    """Summary representation of a tracked incident."""

    model_config = ConfigDict(from_attributes=True)

    incident_id: str
    title: str
    summary: str
    subsystem: str
    severity: IncidentSeverity
    status: IncidentStatus
    linked_alert_ids: List[str] = Field(default_factory=list)
    linked_correlation_ids: List[str] = Field(default_factory=list)
    linked_recommendation_id: Optional[str] = None
    copilot_summary: Optional[str] = None
    created_by: str
    assigned_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IncidentDetail(IncidentRead):
    """Full incident record including linked artifacts and chronological audit logs."""

    logs: List[IncidentLogRead] = Field(default_factory=list)
    linked_recommendation: Optional[RecommendationDetail] = None
    linked_alerts: List[AlertRead] = Field(default_factory=list)
    linked_correlations: List[CorrelationRead] = Field(default_factory=list)


class IncidentListResponse(BaseModel):
    """Paginated list of incidents with aggregate status summary."""

    total: int
    limit: int
    offset: int
    summary: IncidentSummaryCounts
    items: List[IncidentRead]
