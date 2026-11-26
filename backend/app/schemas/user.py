"""Pydantic schemas for User representation, RBAC, and Auth (never exposing password_hash)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RbacRole = Literal["ADMIN", "OPERATOR", "VIEWER"]
UserRole = Literal["ADMIN", "OPERATOR", "VIEWER", "admin", "operator", "viewer", "analyst"]


class UserCreate(BaseModel):
    """Input schema for creating a user."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "OPERATOR"


class UserRead(BaseModel):
    """Public representation of a user (excludes password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool = True
    created_at: datetime


class LoginRequest(BaseModel):
    """Credentials for obtaining a signed RBAC session token."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class ActorRead(BaseModel):
    """Resolved current operator/viewer/admin actor context."""

    username: str
    role: RbacRole
    auth_mode: Literal["bearer", "header", "demo_default"]
    user_id: Optional[int] = None


class TokenResponse(BaseModel):
    """Bearer token response for /api/v1/auth/login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead


class AuthMeResponse(BaseModel):
    """Current authenticated or demo actor context."""

    actor: ActorRead
    user: Optional[UserRead] = None
