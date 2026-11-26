"""FastAPI RBAC dependencies supporting Bearer tokens, demo role headers, and default OPERATOR mode."""

from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import RbacRole, decode_access_token, normalize_role
from app.db.session import get_db
from app.models.user import User


@dataclass(frozen=True)
class ActorContext:
    """Authenticated or demo operator context attached to an API request."""

    username: str
    role: RbacRole
    auth_mode: str  # "bearer" | "header" | "demo_default"
    user_id: Optional[int] = None


def get_current_actor(
    request: Request,
    db: Session = Depends(get_db),
) -> ActorContext:
    """Resolve current actor from Bearer token, X-Operator-Role header, or OPERATOR demo default."""
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        settings = get_settings()
        try:
            payload = decode_access_token(token, settings.jwt_secret_key)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication token: {exc}",
            ) from exc

        username = str(payload["sub"])
        token_role = normalize_role(str(payload.get("role", ""))) or "OPERATOR"
        uid = payload.get("uid")

        try:
            user_row = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
            if user_row is not None:
                if not user_row.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User account is inactive.",
                    )
                resolved_role = normalize_role(user_row.role) or token_role
                return ActorContext(
                    username=user_row.username,
                    role=resolved_role,
                    auth_mode="bearer",
                    user_id=user_row.id,
                )
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001
            pass

        return ActorContext(
            username=username,
            role=token_role,
            auth_mode="bearer",
            user_id=int(uid) if isinstance(uid, int) else None,
        )

    role_header = request.headers.get("X-Operator-Role")
    if role_header and role_header.strip():
        normalized = normalize_role(role_header)
        if normalized is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unsupported operator role '{role_header.strip()}'.",
            )
        name_header = (request.headers.get("X-Operator-Name") or "").strip()
        return ActorContext(
            username=name_header or f"demo-{normalized.lower()}",
            role=normalized,
            auth_mode="header",
            user_id=None,
        )

    return ActorContext(
        username="flight-ops-demo",
        role="OPERATOR",
        auth_mode="demo_default",
        user_id=None,
    )


def require_roles(*allowed_roles: RbacRole) -> Callable[[ActorContext], ActorContext]:
    """Enforce that the resolved actor holds one of the allowed RBAC roles."""
    allowed_set = set(allowed_roles)

    def _dependency(actor: ActorContext = Depends(get_current_actor)) -> ActorContext:
        if actor.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{actor.role}' is read-only or lacks permission for this action. "
                    f"Required role: {' or '.join(allowed_roles)}."
                ),
            )
        return actor

    return _dependency
