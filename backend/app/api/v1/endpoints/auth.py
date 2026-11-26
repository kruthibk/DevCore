"""Authentication endpoints: register, login, logout (token revocation), and current user."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rbac import ActorContext, get_current_actor
from app.core.security import (
    create_access_token,
    hash_password,
    normalize_role,
    verify_password,
)
from app.db.session import get_db
from app.models.token_revocation import RevokedToken
from app.models.user import User
from app.schemas.user import (
    ActorRead,
    AuthMeResponse,
    LoginRequest,
    LogoutResponse,
    RegisterRequest,
    TokenResponse,
    UserRead,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new OPERATOR account (self-elevation to ADMIN is prohibited)",
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    cleaned_username = payload.username.strip()
    cleaned_email = payload.email.strip().lower()

    existing = db.execute(
        select(User).where(
            or_(User.username == cleaned_username, User.email == cleaned_email)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this username or email already exists.",
        )

    user_row = User(
        username=cleaned_username,
        email=cleaned_email,
        password_hash=hash_password(payload.password),
        role="OPERATOR",  # Always assign OPERATOR on public registration
        is_active=True,
    )
    db.add(user_row)
    db.commit()
    db.refresh(user_row)

    settings = get_settings()
    expires_seconds = settings.jwt_expire_minutes * 60
    token = create_access_token(
        subject=user_row.username,
        role="OPERATOR",
        secret_key=settings.jwt_secret_key,
        user_id=user_row.id,
        expires_seconds=expires_seconds,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(
        access_token=token,
        expires_in=expires_seconds,
        user=UserRead.model_validate(user_row),
    )


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate against PostgreSQL users and issue an HMAC-SHA256 JWT",
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
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Contact an administrator.",
        )

    settings = get_settings()
    expires_seconds = settings.jwt_expire_minutes * 60
    resolved_role = normalize_role(user_row.role) or "OPERATOR"
    token = create_access_token(
        subject=user_row.username,
        role=resolved_role,
        secret_key=settings.jwt_secret_key,
        user_id=user_row.id,
        expires_seconds=expires_seconds,
        algorithm=settings.jwt_algorithm,
    )
    return TokenResponse(
        access_token=token,
        expires_in=expires_seconds,
        user=UserRead.model_validate(user_row),
    )


@auth_router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke the active JWT token identifier (jti) so it can no longer be used",
)
def logout(
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> LogoutResponse:
    existing = db.execute(
        select(RevokedToken).where(RevokedToken.jti == actor.jti)
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            RevokedToken(
                jti=actor.jti,
                username=actor.username,
                user_id=actor.user_id,
                expires_at=datetime.fromtimestamp(actor.token_exp, tz=timezone.utc),
            )
        )
        db.commit()
    return LogoutResponse(message=f"Session for '{actor.username}' revoked.")


@auth_router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Return the authenticated current user profile and RBAC role",
)
def get_me(
    actor: ActorContext = Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> AuthMeResponse:
    user_row = db.execute(select(User).where(User.id == actor.user_id)).scalar_one_or_none()
    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user record not found.",
        )
    return AuthMeResponse(
        actor=ActorRead(
            username=actor.username,
            role=actor.role,
            auth_mode="bearer",
            user_id=actor.user_id,
        ),
        user=UserRead.model_validate(user_row),
    )
