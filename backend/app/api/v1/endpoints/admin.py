"""ADMIN-only endpoints for user account management, role assignment, and audit overview."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import ActorContext, require_roles
from app.core.security import normalize_role
from app.db.session import get_db
from app.models.incident import Incident
from app.models.token_revocation import RevokedToken
from app.models.user import User
from app.models.verification import OperatorDecision, Recommendation
from app.schemas.user import (
    AdminAuditSummary,
    AdminUserRoleUpdate,
    AdminUserStatusUpdate,
    AdminUsersResponse,
    UserRead,
)

router = APIRouter(prefix="/admin", tags=["Admin Management"])

ROLE_PERMISSION_MATRIX = {
    "OPERATOR": [
        "View telemetry, alerts, correlations, and incident history",
        "Query AI Copilot and submit recommendations to Verification Wall",
        "Approve, reject, or request investigation on verified/reviewable items",
        "Create incidents and append operator audit notes",
    ],
    "ADMIN": [
        "All OPERATOR permissions",
        "Manage user accounts (activate/deactivate) and assign roles",
        "Control telemetry simulator faults and rebuild FAISS runbook index",
        "Inspect system-level verification and session revocation audit counts",
    ],
}


@router.get(
    "/users",
    response_model=AdminUsersResponse,
    summary="List all user accounts and system-level audit metrics (ADMIN only)",
)
def list_admin_users(
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("ADMIN")),
) -> AdminUsersResponse:
    rows = db.execute(select(User).order_by(User.id.asc())).scalars().all()
    users_out = [UserRead.model_validate(u) for u in rows]

    admin_count = sum(1 for u in rows if normalize_role(u.role) == "ADMIN")
    operator_count = sum(1 for u in rows if normalize_role(u.role) == "OPERATOR")
    active_count = sum(1 for u in rows if u.is_active)

    ver_counts = dict(
        db.execute(
            select(Recommendation.latest_verification_status, func.count(Recommendation.id)).group_by(
                Recommendation.latest_verification_status
            )
        ).all()
    )
    total_recs = sum(int(v) for v in ver_counts.values())
    total_decisions = int(db.execute(select(func.count(OperatorDecision.id))).scalar() or 0)
    total_incidents = int(db.execute(select(func.count(Incident.id))).scalar() or 0)
    revoked_count = int(db.execute(select(func.count(RevokedToken.id))).scalar() or 0)

    return AdminUsersResponse(
        users=users_out,
        audit_summary=AdminAuditSummary(
            total_users=len(rows),
            active_users=active_count,
            admin_users=admin_count,
            operator_users=operator_count,
            total_recommendations=total_recs,
            verified_recommendations=int(ver_counts.get("VERIFIED", 0)),
            needs_review_recommendations=int(ver_counts.get("NEEDS_REVIEW", 0)),
            rejected_recommendations=int(ver_counts.get("REJECTED", 0)),
            total_decisions=total_decisions,
            total_incidents=total_incidents,
            revoked_tokens=revoked_count,
        ),
        role_matrix=ROLE_PERMISSION_MATRIX,
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=UserRead,
    summary="Assign a user's RBAC role (ADMIN only; cannot alter own role)",
)
def update_user_role(
    user_id: int,
    payload: AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("ADMIN")),
) -> UserRead:
    if user_id == actor.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators cannot modify their own role.",
        )
    target = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User id={user_id} not found.",
        )
    target.role = payload.role
    db.commit()
    db.refresh(target)
    return UserRead.model_validate(target)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserRead,
    summary="Activate or deactivate a user account (ADMIN only; cannot deactivate self)",
)
def update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    actor: ActorContext = Depends(require_roles("ADMIN")),
) -> UserRead:
    if user_id == actor.user_id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrators cannot deactivate their own account.",
        )
    target = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User id={user_id} not found.",
        )
    target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return UserRead.model_validate(target)
