"""Pydantic schemas for User representation (never exposing password_hash)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRole = Literal["operator", "analyst", "admin"]


class UserCreate(BaseModel):
    """Input schema for creating a user."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "operator"


class UserRead(BaseModel):
    """Public representation of a user (excludes password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    role: UserRole
    created_at: datetime
