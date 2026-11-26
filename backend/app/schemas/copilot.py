"""Pydantic schemas for Runbook Ingestion, FAISS Retrieval, and AI Copilot APIs."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RunbookManifestEntry(BaseModel):
    """Single runbook declaration inside backend/data/runbooks/manifest.json."""

    runbook_id: str
    filename: str
    version: str
    subsystem: str
    subsystem_display_name: str
    title: str
    document_type: str
    anomaly_ids: List[str]
    keywords: List[str]
    supported_simulator_channels: List[str] = Field(default_factory=list)
    ownership_scope: str = ""


class RunbookManifestSchema(BaseModel):
    """Validated runbook knowledge-base manifest."""

    manifest_version: str
    knowledge_base: str
    indexing_status: str
    supported_simulator_channels: List[str]
    unsupported_candidate_fields_policy: str
    subsystem_ownership: Dict[str, str]
    safety_rules: List[str]
    runbooks: List[RunbookManifestEntry]


class RunbookChunk(BaseModel):
    """Deterministic Markdown-aware chunk with traceable provenance metadata."""

    chunk_id: str
    runbook_id: str
    document_name: str
    document_title: str
    version: str
    subsystem: str
    anomaly_ids: List[str] = Field(default_factory=list)
    section_heading: str
    section_path: str
    document_type: str
    keywords: List[str] = Field(default_factory=list)
    text: str
    content_hash: str
    char_count: int


class RetrievedEvidenceChunk(BaseModel):
    """Retrieved runbook chunk returned by semantic FAISS search."""

    chunk_id: str
    runbook_id: str
    document_name: str
    document_title: str
    version: str
    subsystem: str
    anomaly_ids: List[str] = Field(default_factory=list)
    section_heading: str
    section_path: str
    similarity_score: float = Field(..., ge=-1.0, le=1.0)
    ranking_score: float
    snippet: str
    text: str


class CitationItem(BaseModel):
    """Traceable citation verified against retrieved runbook chunks."""

    chunk_id: str
    runbook_id: str
    document_name: str
    section_heading: str
    subsystem: str
    anomaly_ids: List[str] = Field(default_factory=list)
    similarity_score: float


class CopilotAnswer(BaseModel):
    """Structured, cautious investigative guidance generated from retrieved evidence."""

    anomaly_summary: str
    verified_observations: List[str] = Field(default_factory=list)
    possible_explanations: List[str] = Field(default_factory=list)
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_or_missing_evidence: List[str] = Field(default_factory=list)
    recommended_investigative_checks: List[str] = Field(default_factory=list)
    uncertainty_and_limitations: List[str] = Field(default_factory=list)
    citations: List[CitationItem] = Field(default_factory=list)


class VerifiedTelemetryContext(BaseModel):
    """Verified telemetry, alert, and correlation observations supplied as ground truth."""

    satellite_id: str = "SAT-01"
    supported_channels: List[str] = Field(default_factory=list)
    latest_readings: Dict[str, Any] = Field(default_factory=dict)
    alert: Optional[Dict[str, Any]] = None
    correlation: Optional[Dict[str, Any]] = None
    notes: List[str] = Field(default_factory=list)


class CopilotStatusResponse(BaseModel):
    """Index health, embedding metadata, and LLM availability report."""

    index_status: Literal["READY", "MISSING", "CORRUPTED"]
    index_available: bool
    indexing_status: str
    document_count: int
    chunk_count: int
    embedding_model: str
    embedding_dim: Optional[int] = None
    index_path: str
    llm_available: bool
    llm_provider: str
    llm_model: Optional[str] = None
    diagnostic_message: str
    supported_channels: List[str] = Field(default_factory=list)
    runbooks: List[Dict[str, Any]] = Field(default_factory=list)
    last_indexed_at: Optional[str] = None


class CopilotAskRequest(BaseModel):
    """Request payload for asking the SAT-TRIAGE AI Copilot."""

    question: str = Field(..., max_length=2000)
    satellite_id: str = Field(default="SAT-01", max_length=32)
    subsystem: Optional[str] = Field(default=None, max_length=64)
    anomaly_id: Optional[str] = Field(default=None, max_length=32)
    alert_id: Optional[str] = Field(default=None, max_length=64)
    correlation_id: Optional[str] = Field(default=None, max_length=64)
    top_k: int = Field(default=5, ge=1, le=10)
    include_live_telemetry: bool = True


class CopilotAskResponse(BaseModel):
    """Grounded RAG retrieval + structured Copilot response envelope."""

    question: str
    generation_status: Literal[
        "GENERATED",
        "LLM_UNAVAILABLE",
        "INSUFFICIENT_EVIDENCE",
        "INDEX_UNAVAILABLE",
        "MALFORMED_LLM_RESPONSE",
        "LLM_ERROR",
    ]
    llm_available: bool
    llm_provider: str
    llm_model: Optional[str] = None
    llm_unavailable_reason: Optional[str] = None
    evidence_sufficient: bool
    evidence_message: str
    verified_context: VerifiedTelemetryContext
    retrieved_evidence: List[RetrievedEvidenceChunk] = Field(default_factory=list)
    answer: Optional[CopilotAnswer] = None
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str
    timestamp: datetime
