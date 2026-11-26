"""REST endpoints for Incident Registry and Audit Trail management."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import ActorContext, require_roles
from app.db.session import get_db
from app.realtime.socket_manager import emit_incident_updated
from app.schemas.incidents import (
    IncidentCreate,
    IncidentDetail,
    IncidentListResponse,
    IncidentLogCreate,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate,
)
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incidents & Audit Trail"])


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List tracked incidents and aggregate status counts",
)
def list_incidents(
    status_filter: Optional[IncidentStatus] = Query(default=None, alias="status"),
    severity: Optional[IncidentSeverity] = Query(default=None),
    subsystem: Optional[str] = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> IncidentListResponse:
    items, total, summary = IncidentService.list_incidents(
        db=db,
        status_filter=status_filter,
        severity_filter=severity,
        subsystem_filter=subsystem,
        limit=limit,
        offset=offset,
    )
    return IncidentListResponse(
        total=total,
        limit=limit,
        offset=offset,
        summary=summary,
        items=items,
    )


@router.post(
    "",
    response_model=IncidentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create an incident and record its initial CREATED audit entry",
)
async def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> IncidentDetail:
    detail = IncidentService.create_incident(db=db, payload=payload, actor=actor)
    await emit_incident_updated({"incident_id": detail.incident_id, "status": detail.status})
    return detail


@router.get(
    "/{incident_id}",
    response_model=IncidentDetail,
    summary="Get full incident details and chronological audit logs",
)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> IncidentDetail:
    return IncidentService.get_incident_detail(db=db, incident_id=incident_id)


@router.patch(
    "/{incident_id}",
    response_model=IncidentDetail,
    summary="Transition incident status or assignee and record audit trail",
)
async def update_incident(
    incident_id: str,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> IncidentDetail:
    detail = IncidentService.update_incident(
        db=db,
        incident_id=incident_id,
        payload=payload,
        actor=actor,
    )
    await emit_incident_updated({"incident_id": detail.incident_id, "status": detail.status})
    return detail


@router.post(
    "/{incident_id}/logs",
    response_model=IncidentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Append an investigation note to an incident audit trail",
)
async def add_incident_log(
    incident_id: str,
    payload: IncidentLogCreate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> IncidentDetail:
    detail = IncidentService.add_log_note(
        db=db,
        incident_id=incident_id,
        payload=payload,
        actor=actor,
    )
    await emit_incident_updated({"incident_id": detail.incident_id, "status": detail.status})
    return detail
