"""Pydantic schemas for anomaly detection, sensor integrity, and alert management."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict

AlertType = Literal[
    "STATISTICAL_ANOMALY",
    "RATE_OF_CHANGE",
    "ENGINEERING_LIMIT",
    "SENSOR_MISSING",
    "SENSOR_FROZEN",
    "SENSOR_INVALID",
    "SENSOR_STALE",
]
AlertSeverity = Literal["INFO", "WARNING", "CRITICAL"]
AlertStatus = Literal["ACTIVE", "ACKNOWLEDGED", "RESOLVED"]
IntegrityStatus = Literal["OK", "MISSING", "FROZEN", "INVALID", "STALE", "STREAM_INACTIVE", "NO_DATA"]


class AlertRead(BaseModel):
    """Serialized alert returned by REST APIs and Socket.IO events."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: str
    satellite_id: str
    sensor_name: str
    alert_type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    observed_value: Optional[float] = None
    expected_range: Optional[str] = None
    z_score: Optional[float] = None
    reason_code: str
    evidence: Dict[str, Any]
    first_detected_at: datetime
    last_detected_at: datetime
    occurrence_count: int
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AlertSummaryCounts(BaseModel):
    """Aggregate alert counts derived from persisted database records."""

    total: int
    active: int
    acknowledged: int
    resolved: int
    critical_active: int
    warning_active: int
    info_active: int


class AlertListResponse(BaseModel):
    """Paginated response for GET /api/v1/alerts."""

    total: int
    limit: int
    offset: int
    summary: AlertSummaryCounts
    items: List[AlertRead]


class SensorIntegrityFinding(BaseModel):
    """Structured finding emitted by SensorIntegrityService."""

    satellite_id: str
    sensor_name: str
    integrity_status: Literal["MISSING", "FROZEN", "INVALID", "STALE"]
    severity: AlertSeverity
    observed_value: Optional[float] = None
    detected_at: datetime
    reason_code: str
    reason: str
    evidence: Dict[str, Any]


class SensorChannelHealth(BaseModel):
    """Current integrity and statistical baseline snapshot for a single sensor."""

    sensor_name: str
    unit: str
    integrity_status: IntegrityStatus
    last_received_at: Optional[datetime] = None
    last_value: Optional[float] = None
    baseline_samples: int
    baseline_mean: Optional[float] = None
    baseline_std: Optional[float] = None
    issue_reason: Optional[str] = None


class DetectionStatusResponse(BaseModel):
    """Response for GET /api/v1/detection/status."""

    engine_active: bool
    stream_state: Literal["ACTIVE", "STREAM_INACTIVE"]
    simulator_running: bool
    last_processed_at: Optional[datetime] = None
    processed_sample_count: int
    active_alert_count: int
    integrity_issue_count: int
    persisted_alerts_count: int
    failed_persist_count: int
    last_persistence_error: Optional[str] = None
    sensor_states: List[SensorChannelHealth]
    config_summary: Dict[str, Any]
    timestamp: datetime


class SensorLimitsSchema(BaseModel):
    """Serialized engineering & physical limits for a sensor channel."""

    unit: str
    engineering_warning: List[float]
    engineering_critical: List[float]
    physical_valid_range: List[float]
    max_rate_per_sec: float
    min_meaningful_std: float


class DetectionConfigResponse(BaseModel):
    """Response for GET /api/v1/detection/config."""

    rolling_window_size: int
    min_baseline_samples: int
    z_score_warning: float
    z_score_critical: float
    frozen_consecutive_samples: int
    stale_timeout_seconds: float
    sensor_limits: Dict[str, SensorLimitsSchema]
