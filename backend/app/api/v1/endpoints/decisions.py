"""REST endpoints for Human Operator Approvals, Rejections, and Investigation Requests."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.rbac import ActorContext, require_roles
from app.db.session import get_db
from app.realtime.socket_manager import emit_incident_updated
from app.schemas.verification import (
    DecisionApproveRequest,
    DecisionHistoryResponse,
    DecisionReasonRequest,
    RecommendationDetail,
)
from app.services.verification_wall import DecisionService

router = APIRouter(prefix="/decisions", tags=["Operator Decisions"])


@router.get(
    "/history",
    response_model=DecisionHistoryResponse,
    summary="List chronological human operator decision history",
)
def list_decision_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> DecisionHistoryResponse:
    items, total = DecisionService.list_history(db=db, limit=limit, offset=offset)
    return DecisionHistoryResponse(total=total, items=items)


@router.post(
    "/{recommendation_id}/approve",
    response_model=RecommendationDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Record human operator approval (never executes spacecraft commands; blocks REJECTED items)",
)
async def approve_recommendation(
    recommendation_id: str,
    payload: DecisionApproveRequest = DecisionApproveRequest(),
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> RecommendationDetail:
    detail = DecisionService.record_decision(
        db=db,
        recommendation_id=recommendation_id,
        decision="APPROVED",
        actor=actor,
        notes=payload.notes,
        incident_id=payload.incident_id,
    )
    if detail.linked_incident_id:
        await emit_incident_updated({"incident_id": detail.linked_incident_id})
    return detail


@router.post(
    "/{recommendation_id}/reject",
    response_model=RecommendationDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Reject a recommendation with a mandatory operator reason",
)
async def reject_recommendation(
    recommendation_id: str,
    payload: DecisionReasonRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> RecommendationDetail:
    detail = DecisionService.record_decision(
        db=db,
        recommendation_id=recommendation_id,
        decision="REJECTED",
        actor=actor,
        reason=payload.reason,
        notes=payload.notes,
        incident_id=payload.incident_id,
    )
    if detail.linked_incident_id:
        await emit_incident_updated({"incident_id": detail.linked_incident_id})
    return detail


@router.post(
    "/{recommendation_id}/request-investigation",
    response_model=RecommendationDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Request further operator investigation with a mandatory reason",
)
async def request_investigation(
    recommendation_id: str,
    payload: DecisionReasonRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> RecommendationDetail:
    detail = DecisionService.record_decision(
        db=db,
        recommendation_id=recommendation_id,
        decision="INVESTIGATION_REQUESTED",
        actor=actor,
        reason=payload.reason,
        notes=payload.notes,
        incident_id=payload.incident_id,
    )
    if detail.linked_incident_id:
        await emit_incident_updated({"incident_id": detail.linked_incident_id})
    return detail
