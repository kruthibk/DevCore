"""FastAPI JWT authentication and role-based access control dependencies."""

from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import RbacRole, decode_access_token, normalize_role
from app.db.session import get_db
from app.models.token_revocation import RevokedToken
from app.models.user import User


@dataclass(frozen=True)
class ActorContext:
    """Authenticated user context resolved from a verified JWT."""

    username: str
    role: RbacRole
    auth_mode: str  # "bearer"
    user_id: int
    jti: str
    token_exp: int


def get_current_actor(
    request: Request,
    db: Session = Depends(get_db),
) -> ActorContext:
    """Strictly verify Bearer JWT, check token revocation, and load active User from DB."""
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a valid Bearer JWT.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()
    try:
        payload = decode_access_token(
            token,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    jti = str(payload["jti"])
    revoked = db.execute(select(RevokedToken).where(RevokedToken.jti == jti)).scalar_one_or_none()
    if revoked is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = str(payload["sub"])
    uid = payload.get("uid")
    stmt = select(User).where(User.id == int(uid)) if isinstance(uid, int) else select(User).where(User.username == username)
    user_row = db.execute(stmt).scalar_one_or_none()

    if user_row is None or user_row.username != username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user record not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    resolved_role = normalize_role(user_row.role) or "OPERATOR"
    return ActorContext(
        username=user_row.username,
        role=resolved_role,
        auth_mode="bearer",
        user_id=user_row.id,
        jti=jti,
        token_exp=int(payload["exp"]),
    )


def require_roles(*allowed_roles: RbacRole) -> Callable[[ActorContext], ActorContext]:
    """Enforce that the authenticated actor holds one of the allowed RBAC roles."""
    allowed_set = set(allowed_roles)

    def _dependency(actor: ActorContext = Depends(get_current_actor)) -> ActorContext:
        if actor.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{actor.role}' lacks permission for this operation. "
                    f"Required role: {' or '.join(allowed_roles)}."
                ),
            )
        return actor

    return _dependency
