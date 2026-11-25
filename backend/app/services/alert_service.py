"""Database persistence, deduplication, and lifecycle service for alerts."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.alert import Alert
from app.schemas.alerts import (
    AlertRead,
    AlertSeverity,
    AlertStatus,
    AlertSummaryCounts,
    AlertType,
)

SEVERITY_RANK: Dict[str, int] = {"INFO": 1, "WARNING": 2, "CRITICAL": 3}


class AlertNotFoundError(AppException):
    """Raised when an alert_id does not exist."""

    def __init__(self, alert_id: str) -> None:
        super().__init__(
            message=f"Alert '{alert_id}' was not found.",
            code="ALERT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


@dataclass
class AlertCandidate:
    """Normalized alert input before DB deduplication and persistence."""

    satellite_id: str
    sensor_name: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    observed_value: Optional[float]
    expected_range: Optional[str]
    z_score: Optional[float]
    reason_code: str
    evidence: Dict[str, Any]
    detected_at: datetime


class AlertService:
    """Handles alert deduplication, DB persistence, querying, and operator state transitions."""

    @staticmethod
    def upsert_findings(
        db: Session,
        candidates: List[AlertCandidate],
        cooldown_seconds: float = 10.0,
    ) -> Tuple[List[AlertRead], List[AlertRead]]:
        """Persist new alerts or update active/acknowledged duplicates in one transaction.

        Returns (newly_created_alerts, updated_alerts).
        """
        if not candidates:
            return [], []

        created_orms: List[Alert] = []
        updated_orms: List[Alert] = []

        for cand in candidates:
            existing = db.execute(
                select(Alert)
                .where(
                    Alert.satellite_id == cand.satellite_id,
                    Alert.sensor_name == cand.sensor_name,
                    Alert.alert_type == cand.alert_type,
                    Alert.status.in_(("ACTIVE", "ACKNOWLEDGED")),
                )
                .order_by(desc(Alert.last_detected_at), desc(Alert.id))
                .limit(1)
            ).scalar_one_or_none()

            if existing is not None:
                last_ts = existing.last_detected_at
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                det_ts = cand.detected_at
                if det_ts.tzinfo is None:
                    det_ts = det_ts.replace(tzinfo=timezone.utc)

                new_rank = SEVERITY_RANK.get(cand.severity, 0)
                old_rank = SEVERITY_RANK.get(existing.severity, 0)
                is_escalation = new_rank > old_rank

                if (
                    not is_escalation
                    and cooldown_seconds > 0
                    and (det_ts - last_ts).total_seconds() < cooldown_seconds
                ):
                    continue

                if new_rank >= old_rank:
                    # Update full atomic snapshot so severity, title, description, observed_value,
                    # z_score, and evidence always originate from the exact same evaluation.
                    existing.severity = cand.severity
                    existing.title = cand.title
                    existing.description = cand.description
                    existing.observed_value = cand.observed_value
                    existing.expected_range = cand.expected_range
                    existing.z_score = cand.z_score
                    existing.reason_code = cand.reason_code
                    existing.evidence = cand.evidence
                else:
                    # Preserve peak-severity atomic snapshot without mixing lower-severity values
                    merged_evidence = dict(existing.evidence or {})
                    merged_evidence["latest_observed_value"] = cand.observed_value
                    merged_evidence["latest_observed_at"] = det_ts.isoformat()
                    existing.evidence = merged_evidence

                existing.last_detected_at = cand.detected_at
                existing.occurrence_count += 1
                updated_orms.append(existing)
            else:
                new_alert = Alert(
                    alert_id=f"ALT-{uuid4().hex[:10].upper()}",
                    satellite_id=cand.satellite_id,
                    sensor_name=cand.sensor_name,
                    alert_type=cand.alert_type,
                    severity=cand.severity,
                    status="ACTIVE",
                    title=cand.title,
                    description=cand.description,
                    observed_value=cand.observed_value,
                    expected_range=cand.expected_range,
                    z_score=cand.z_score,
                    reason_code=cand.reason_code,
                    evidence=cand.evidence,
                    first_detected_at=cand.detected_at,
                    last_detected_at=cand.detected_at,
                    occurrence_count=1,
                )
                db.add(new_alert)
                created_orms.append(new_alert)

        db.commit()
        for row in created_orms:
            db.refresh(row)
        for row in updated_orms:
            db.refresh(row)

        return (
            [AlertRead.model_validate(r) for r in created_orms],
            [AlertRead.model_validate(r) for r in updated_orms],
        )

    @staticmethod
    def resolve_recovered_alerts(
        db: Session,
        satellite_id: str,
        sensor_names: List[str],
        resolved_at: datetime,
        resolution_reason: str = "Automatic recovery verified across consecutive nominal samples.",
    ) -> List[AlertRead]:
        """Resolve open alerts for recovered sensors without erasing alert history."""
        if not sensor_names:
            return []

        open_rows = (
            db.execute(
                select(Alert).where(
                    Alert.satellite_id == satellite_id,
                    Alert.sensor_name.in_(sensor_names),
                    Alert.status.in_(("ACTIVE", "ACKNOWLEDGED")),
                )
            )
            .scalars()
            .all()
        )
        if not open_rows:
            return []

        for row in open_rows:
            row.status = "RESOLVED"
            row.resolved_at = resolved_at
            ev = dict(row.evidence or {})
            ev["resolution_note"] = resolution_reason
            ev["auto_resolved_at"] = resolved_at.isoformat()
            row.evidence = ev

        db.commit()
        for row in open_rows:
            db.refresh(row)

        return [AlertRead.model_validate(r) for r in open_rows]

    @staticmethod
    def get_summary_counts(db: Session, satellite_id: Optional[str] = None) -> AlertSummaryCounts:
        """Compute exact aggregate alert counts directly from PostgreSQL."""
        base_filter = [Alert.satellite_id == satellite_id] if satellite_id else []

        total = db.execute(select(func.count()).select_from(Alert).where(*base_filter)).scalar_one()
        active = db.execute(
            select(func.count()).select_from(Alert).where(*base_filter, Alert.status == "ACTIVE")
        ).scalar_one()
        acknowledged = db.execute(
            select(func.count())
            .select_from(Alert)
            .where(*base_filter, Alert.status == "ACKNOWLEDGED")
        ).scalar_one()
        resolved = db.execute(
            select(func.count()).select_from(Alert).where(*base_filter, Alert.status == "RESOLVED")
        ).scalar_one()

        open_statuses = ("ACTIVE", "ACKNOWLEDGED")
        critical_active = db.execute(
            select(func.count())
            .select_from(Alert)
            .where(*base_filter, Alert.status.in_(open_statuses), Alert.severity == "CRITICAL")
        ).scalar_one()
        warning_active = db.execute(
            select(func.count())
            .select_from(Alert)
            .where(*base_filter, Alert.status.in_(open_statuses), Alert.severity == "WARNING")
        ).scalar_one()
        info_active = db.execute(
            select(func.count())
            .select_from(Alert)
            .where(*base_filter, Alert.status.in_(open_statuses), Alert.severity == "INFO")
        ).scalar_one()

        return AlertSummaryCounts(
            total=total,
            active=active,
            acknowledged=acknowledged,
            resolved=resolved,
            critical_active=critical_active,
            warning_active=warning_active,
            info_active=info_active,
        )

    @staticmethod
    def list_alerts(
        db: Session,
        satellite_id: Optional[str] = None,
        sensor_name: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None,
        alert_status: Optional[AlertStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AlertRead], int, AlertSummaryCounts]:
        """List alerts ordered newest-first with filters and bounded pagination."""
        filters = []
        if satellite_id is not None:
            filters.append(Alert.satellite_id == satellite_id)
        if sensor_name is not None:
            filters.append(Alert.sensor_name == sensor_name)
        if severity is not None:
            filters.append(Alert.severity == severity)
        if alert_type is not None:
            filters.append(Alert.alert_type == alert_type)
        if alert_status is not None:
            filters.append(Alert.status == alert_status)

        total = db.execute(select(func.count()).select_from(Alert).where(*filters)).scalar_one()
        rows = (
            db.execute(
                select(Alert)
                .where(*filters)
                .order_by(desc(Alert.last_detected_at), desc(Alert.id))
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        summary = AlertService.get_summary_counts(db, satellite_id=satellite_id)
        return [AlertRead.model_validate(r) for r in rows], total, summary

    @staticmethod
    def get_alert_by_id(db: Session, alert_id: str) -> AlertRead:
        """Fetch a single alert by its public alert_id."""
        row = db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
        if row is None:
            raise AlertNotFoundError(alert_id)
        return AlertRead.model_validate(row)

    @staticmethod
    def acknowledge_alert(db: Session, alert_id: str) -> AlertRead:
        """Transition an alert to ACKNOWLEDGED (idempotent if already ACKNOWLEDGED)."""
        row = db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
        if row is None:
            raise AlertNotFoundError(alert_id)
        if row.status == "RESOLVED":
            raise AppException(
                message="Resolved alerts cannot be moved back to ACKNOWLEDGED.",
                code="INVALID_ALERT_TRANSITION",
                status_code=status.HTTP_409_CONFLICT,
            )
        if row.status != "ACKNOWLEDGED":
            row.status = "ACKNOWLEDGED"
            row.acknowledged_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
        return AlertRead.model_validate(row)

    @staticmethod
    def resolve_alert(db: Session, alert_id: str) -> AlertRead:
        """Transition an alert to RESOLVED with timestamp."""
        row = db.execute(select(Alert).where(Alert.alert_id == alert_id)).scalar_one_or_none()
        if row is None:
            raise AlertNotFoundError(alert_id)
        if row.status != "RESOLVED":
            row.status = "RESOLVED"
            row.resolved_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(row)
        return AlertRead.model_validate(row)
