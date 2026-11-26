"""REST endpoints for the Phase 8 deterministic Verification Wall."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rbac import ActorContext, require_roles
from app.db.session import get_db
from app.schemas.verification import (
    RecommendationDetail,
    RecommendationListResponse,
    VerificationEvaluateRequest,
    VerificationRead,
    VerificationStatus,
)
from app.services.verification_wall import VerificationService

router = APIRouter(prefix="/verification", tags=["Verification Wall"])


@router.post(
    "/evaluate",
    response_model=RecommendationDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an AI or simulator recommendation for deterministic Verification Wall checks",
)
def evaluate_recommendation(
    payload: VerificationEvaluateRequest,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> RecommendationDetail:
    settings = get_settings()
    return VerificationService.evaluate_and_persist(
        db=db,
        payload=payload,
        actor=actor,
        min_similarity=settings.rag_min_similarity,
    )


@router.get(
    "/recommendations",
    response_model=RecommendationListResponse,
    summary="List recommendations submitted to the Verification Wall",
)
def list_recommendations(
    verification_status: Optional[VerificationStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> RecommendationListResponse:
    items, total, summary = VerificationService.list_recommendations(
        db=db,
        verification_status=verification_status,
        limit=limit,
        offset=offset,
    )
    return RecommendationListResponse(total=total, summary=summary, items=items)


@router.get(
    "/recommendations/{recommendation_id}",
    response_model=RecommendationDetail,
    summary="Inspect recommendation, all verification evaluations, and operator decision history",
)
def get_recommendation_detail(
    recommendation_id: str,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> RecommendationDetail:
    return VerificationService.get_recommendation_detail(db=db, recommendation_id=recommendation_id)


@router.get(
    "/{verification_id}",
    response_model=VerificationRead,
    summary="Get an immutable Verification Wall record by verification ID",
)
def get_verification_by_id(
    verification_id: str,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> VerificationRead:
    return VerificationService.get_verification(db=db, verification_id=verification_id)
