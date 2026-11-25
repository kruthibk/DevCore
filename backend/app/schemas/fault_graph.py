"""Pydantic schemas for the hybrid causal fault graph and alert correlations."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.alerts import AlertRead

CorrelationStatus = Literal["ACTIVE", "ACKNOWLEDGED", "DISMISSED"]
SubsystemId = Literal["EPS", "THERMAL", "ADCS", "OBC", "SENSORS"]


class GraphNode(BaseModel):
    """Node in the fault graph (subsystem, sensor, or persisted alert)."""

    id: str
    node_type: Literal["subsystem", "sensor", "alert"]
    label: str
    subsystem: Optional[str] = None
    status: str = "NOMINAL"
    severity: Optional[str] = None
    metadata: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    """Directed edge representing subsystem dependency, telemetry mapping, or alert link."""

    id: str
    source: str
    target: str
    relationship: str
    description: str = ""
    active: bool = False


class EvidenceItem(BaseModel):
    """Structured supporting or contradicting evidence entry."""

    kind: str
    summary: str
    details: Optional[Dict[str, Any]] = None


class CorrelationRead(BaseModel):
    """Serialized persisted correlation record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    correlation_id: str
    satellite_id: str
    rule_code: str
    suspected_subsystem: SubsystemId
    hypothesis: str
    grouping_reason: str
    related_alert_ids: List[str]
    supporting_evidence: List[Dict[str, Any]]
    contradicting_evidence: List[Dict[str, Any]]
    confidence_score: float
    confidence_explanation: str
    status: CorrelationStatus
    window_start: datetime
    window_end: datetime
    acknowledged_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CorrelationDetailResponse(CorrelationRead):
    """Correlation record enriched with full linked Alert objects."""

    related_alerts: List[AlertRead] = []


class CorrelationSummaryCounts(BaseModel):
    """Aggregate correlation counts."""

    total: int
    active: int
    acknowledged: int
    dismissed: int


class CorrelationListResponse(BaseModel):
    """Paginated response for GET /api/v1/fault-graph/correlations."""

    total: int
    limit: int
    offset: int
    summary: CorrelationSummaryCounts
    items: List[CorrelationRead]


class FaultGraphResponse(BaseModel):
    """Full causal fault graph topology + live correlations for GET /api/v1/fault-graph."""

    satellite_id: str
    window_seconds: float
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    correlations: List[CorrelationRead]
    summary: CorrelationSummaryCounts
    disclaimer: str = (
        "Hypotheses identify possible common causes from subsystem rules and temporal "
        "correlation; correlation does not prove causation. Human operators retain final authority."
    )
    timestamp: datetime
