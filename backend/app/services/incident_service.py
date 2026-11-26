"""Service layer for Incident Registry and immutable Audit Trail logs."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.rbac import ActorContext
from app.models.incident import Incident, IncidentLog
from app.schemas.incidents import (
    IncidentCreate,
    IncidentDetail,
    IncidentLogCreate,
    IncidentLogRead,
    IncidentRead,
    IncidentSummaryCounts,
    IncidentUpdate,
)


class IncidentService:
    """Manages persistent incidents and immutable chronological audit entries."""

    @staticmethod
    def _build_summary(db: Session) -> IncidentSummaryCounts:
        rows = db.execute(
            select(Incident.status, func.count(Incident.id)).group_by(Incident.status)
        ).all()
        counts = {row[0]: int(row[1]) for row in rows}
        open_count = counts.get("OPEN", 0)
        investigating_count = counts.get("INVESTIGATING", 0)
        mitigated_count = counts.get("MITIGATED", 0)
        closed_count = counts.get("CLOSED", 0)
        total = open_count + investigating_count + mitigated_count + closed_count
        return IncidentSummaryCounts(
            total=total,
            open=open_count + investigating_count,
            investigating=investigating_count,
            mitigated=mitigated_count,
            closed=closed_count,
            resolved=mitigated_count + closed_count,
        )

    @staticmethod
    def list_incidents(
        db: Session,
        status_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        subsystem_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[IncidentRead], int, IncidentSummaryCounts]:
        stmt = select(Incident)
        count_stmt = select(func.count(Incident.id))

        if status_filter:
            stmt = stmt.where(Incident.status == status_filter)
            count_stmt = count_stmt.where(Incident.status == status_filter)
        if severity_filter:
            stmt = stmt.where(Incident.severity == severity_filter)
            count_stmt = count_stmt.where(Incident.severity == severity_filter)
        if subsystem_filter:
            stmt = stmt.where(Incident.subsystem == subsystem_filter)
            count_stmt = count_stmt.where(Incident.subsystem == subsystem_filter)

        total = int(db.execute(count_stmt).scalar() or 0)
        rows = (
            db.execute(
                stmt.order_by(desc(Incident.updated_at), desc(Incident.id)).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
        summary = IncidentService._build_summary(db)
        return [IncidentRead.model_validate(row) for row in rows], total, summary

    @staticmethod
    def get_incident_detail(db: Session, incident_id: str) -> IncidentDetail:
        row = (
            db.execute(
                select(Incident)
                .options(selectinload(Incident.logs))
                .where(Incident.incident_id == incident_id)
            )
            .scalars()
            .first()
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found.",
            )
        return IncidentDetail.model_validate(row)

    @staticmethod
    def create_incident(
        db: Session,
        payload: IncidentCreate,
        actor: ActorContext,
    ) -> IncidentDetail:
        incident_id = f"INC-{uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        cleaned_alerts = list(dict.fromkeys(a.strip() for a in payload.linked_alert_ids if a.strip()))

        record = Incident(
            incident_id=incident_id,
            title=payload.title.strip(),
            summary=payload.summary.strip(),
            subsystem=payload.subsystem.strip() or "GENERAL",
            severity=payload.severity,
            status="OPEN",
            linked_alert_ids=cleaned_alerts,
            copilot_summary=payload.copilot_summary.strip() if payload.copilot_summary else None,
            created_by=actor.username,
            assigned_to=payload.assigned_to.strip() if payload.assigned_to else actor.username,
            created_at=now,
            updated_at=now,
        )
        initial_note = (
            payload.note.strip()
            if payload.note and payload.note.strip()
            else f"Incident logged by {actor.username} ({actor.role})."
        )
        audit_entry = IncidentLog(
            incident_id=incident_id,
            actor=actor.username,
            role=actor.role,
            action="CREATED",
            from_status=None,
            to_status="OPEN",
            note=initial_note,
            created_at=now,
        )
        db.add(record)
        db.add(audit_entry)
        db.commit()
        return IncidentService.get_incident_detail(db=db, incident_id=incident_id)

    @staticmethod
    def update_incident(
        db: Session,
        incident_id: str,
        payload: IncidentUpdate,
        actor: ActorContext,
    ) -> IncidentDetail:
        row = db.execute(select(Incident).where(Incident.incident_id == incident_id)).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found.",
            )

        now = datetime.now(timezone.utc)
        old_status = row.status
        new_status = payload.status
        assignee_changed = (
            payload.assigned_to is not None
            and payload.assigned_to.strip() != (row.assigned_to or "")
        )

        if payload.assigned_to is not None:
            row.assigned_to = payload.assigned_to.strip() or None

        if new_status is not None and new_status != old_status:
            row.status = new_status
            note_text = (
                payload.note.strip()
                if payload.note and payload.note.strip()
                else f"Status transitioned from {old_status} to {new_status}."
            )
            db.add(
                IncidentLog(
                    incident_id=incident_id,
                    actor=actor.username,
                    role=actor.role,
                    action="STATUS_CHANGE",
                    from_status=old_status,
                    to_status=new_status,
                    note=note_text,
                    created_at=now,
                )
            )
        elif assignee_changed or (payload.note and payload.note.strip()):
            note_parts: List[str] = []
            if assignee_changed:
                note_parts.append(f"Assigned operator updated to '{row.assigned_to or 'unassigned'}'.")
            if payload.note and payload.note.strip():
                note_parts.append(payload.note.strip())
            db.add(
                IncidentLog(
                    incident_id=incident_id,
                    actor=actor.username,
                    role=actor.role,
                    action="NOTE_ADDED",
                    from_status=old_status,
                    to_status=old_status,
                    note=" ".join(note_parts),
                    created_at=now,
                )
            )

        row.updated_at = now
        db.commit()
        return IncidentService.get_incident_detail(db=db, incident_id=incident_id)

    @staticmethod
    def add_log_note(
        db: Session,
        incident_id: str,
        payload: IncidentLogCreate,
        actor: ActorContext,
    ) -> IncidentDetail:
        row = db.execute(select(Incident).where(Incident.incident_id == incident_id)).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident '{incident_id}' not found.",
            )

        now = datetime.now(timezone.utc)
        db.add(
            IncidentLog(
                incident_id=incident_id,
                actor=actor.username,
                role=actor.role,
                action="NOTE_ADDED",
                from_status=row.status,
                to_status=row.status,
                note=payload.note.strip(),
                created_at=now,
            )
        )
        row.updated_at = now
        db.commit()
        return IncidentService.get_incident_detail(db=db, incident_id=incident_id)
