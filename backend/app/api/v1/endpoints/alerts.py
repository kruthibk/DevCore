"""REST endpoints for persisted anomaly and sensor integrity alerts."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.rbac import ActorContext, require_roles
from app.db.session import get_db
from app.realtime.socket_manager import emit_alert_updated, emit_detection_status
from app.schemas.alerts import (
    AlertListResponse,
    AlertRead,
    AlertSeverity,
    AlertStatus,
    AlertType,
)
from app.services.alert_service import AlertService
from app.services.detection_pipeline import DetectionPipelineService, detection_pipeline

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def get_detection_pipeline() -> DetectionPipelineService:
    """Dependency returning the shared detection pipeline service."""
    return detection_pipeline


@router.get(
    "",
    response_model=AlertListResponse,
    summary="List persisted alerts with filters and bounded pagination",
)
def list_alerts(
    satellite_id: Optional[str] = Query(default=None, max_length=32),
    sensor_name: Optional[str] = Query(default=None, max_length=64),
    severity: Optional[AlertSeverity] = Query(default=None),
    alert_type: Optional[AlertType] = Query(default=None),
    status: Optional[AlertStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> AlertListResponse:
    items, total, summary = AlertService.list_alerts(
        db=db,
        satellite_id=satellite_id,
        sensor_name=sensor_name,
        severity=severity,
        alert_type=alert_type,
        alert_status=status,
        limit=limit,
        offset=offset,
    )
    return AlertListResponse(
        total=total,
        limit=limit,
        offset=offset,
        summary=summary,
        items=items,
    )


@router.get(
    "/{alert_id}",
    response_model=AlertRead,
    summary="Get full details and evidence for an alert",
)
def get_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> AlertRead:
    return AlertService.get_alert_by_id(db=db, alert_id=alert_id)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertRead,
    summary="Acknowledge an active alert",
)
async def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    pipeline: DetectionPipelineService = Depends(get_detection_pipeline),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> AlertRead:
    updated = AlertService.acknowledge_alert(db=db, alert_id=alert_id)
    await emit_alert_updated(updated.model_dump(mode="json"))
    status_snapshot = pipeline.build_status(db=db)
    await emit_detection_status(status_snapshot.model_dump(mode="json"))
    return updated


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Resolve an alert",
)
async def resolve_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    pipeline: DetectionPipelineService = Depends(get_detection_pipeline),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> AlertRead:
    updated = AlertService.resolve_alert(db=db, alert_id=alert_id)
    await emit_alert_updated(updated.model_dump(mode="json"))
    status_snapshot = pipeline.build_status(db=db)
    await emit_detection_status(status_snapshot.model_dump(mode="json"))
    return updated
