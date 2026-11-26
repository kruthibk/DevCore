"""Pydantic schemas for User representation, Auth, RBAC, and Admin User Management."""

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

RbacRole = Literal["ADMIN", "OPERATOR", "VIEWER"]
AssignableRole = Literal["ADMIN", "OPERATOR"]
UserRole = Literal["ADMIN", "OPERATOR", "VIEWER", "admin", "operator", "viewer", "analyst"]


class UserCreate(BaseModel):
    """Input schema for creating a user."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "OPERATOR"


class RegisterRequest(BaseModel):
    """Public self-registration payload (role is always assigned server-side as OPERATOR)."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


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
    """Credentials for obtaining a signed JWT access token."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class ActorRead(BaseModel):
    """Resolved authenticated actor context."""

    username: str
    role: RbacRole
    auth_mode: Literal["bearer"] = "bearer"
    user_id: int


class TokenResponse(BaseModel):
    """Bearer token response for /api/v1/auth/login and /register."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserRead


class LogoutResponse(BaseModel):
    """Confirmation of JWT session revocation."""

    status: Literal["logged_out"] = "logged_out"
    message: str


class AuthMeResponse(BaseModel):
    """Current authenticated user profile and actor role."""

    actor: ActorRead
    user: UserRead


class AdminUserRoleUpdate(BaseModel):
    """Admin request to assign a user's RBAC role."""

    role: AssignableRole


class AdminUserStatusUpdate(BaseModel):
    """Admin request to activate or deactivate a user account."""

    is_active: bool


class AdminAuditSummary(BaseModel):
    """System-level audit counts visible to administrators."""

    total_users: int
    active_users: int
    admin_users: int
    operator_users: int
    total_recommendations: int
    verified_recommendations: int
    needs_review_recommendations: int
    rejected_recommendations: int
    total_decisions: int
    total_incidents: int
    revoked_tokens: int


class AdminUsersResponse(BaseModel):
    """Admin user directory paired with system audit counts."""

    users: List[UserRead]
    audit_summary: AdminAuditSummary
    role_matrix: Dict[str, List[str]]
