"""Authentication, RBAC introspection, and user listing endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rbac import ActorContext, get_current_actor
from app.core.security import create_access_token, normalize_role, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    ActorRead,
    AuthMeResponse,
    LoginRequest,
    TokenResponse,
    UserRead,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])
users_router = APIRouter(prefix="/users", tags=["Users"])


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate against the PostgreSQL users table and receive a bearer token",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user_row = db.execute(
        select(User).where(User.username == payload.username.strip())
    ).scalar_one_or_none()

    if user_row is None or not verify_password(payload.password, user_row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )
    if not user_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled.",
        )

    settings = get_settings()
    token = create_access_token(
        subject=user_row.username,
        role=normalize_role(user_row.role) or "OPERATOR",
        secret_key=settings.jwt_secret_key,
        user_id=user_row.id,
    )
    return TokenResponse(
        access_token=token,
        user=UserRead.model_validate(user_row),
    )


@auth_router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Return the resolved RBAC actor (Bearer token, X-Operator-Role header, or default OPERATOR)",
)
def get_me(
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    user_row = db.execute(select(User).where(User.username == actor.username)).scalar_one_or_none()
    return AuthMeResponse(
        actor=ActorRead(
            username=actor.username,
            role=actor.role,
            auth_mode=actor.auth_mode,  # type: ignore[arg-type]
            user_id=actor.user_id,
        ),
        user=UserRead.model_validate(user_row) if user_row is not None else None,
    )


@users_router.get(
    "",
    response_model=List[UserRead],
    summary="List platform users without exposing password hashes",
)
def list_users(
    db: Session = Depends(get_db),
) -> List[UserRead]:
    rows = db.execute(select(User).order_by(User.id.asc())).scalars().all()
    return [UserRead.model_validate(row) for row in rows]
