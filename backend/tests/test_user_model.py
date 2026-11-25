"""Tests for the initial User model, constraints, and password hashing."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserRead


def test_user_creation_hashes_password_and_excludes_hash_from_schema(sqlite_session: Session) -> None:
    raw_password = "TelemetrySecure!2026"
    pw_hash = hash_password(raw_password)
    assert pw_hash != raw_password
    assert verify_password(raw_password, pw_hash) is True
    assert verify_password("wrong-password", pw_hash) is False

    user = User(
        username="flight_director",
        email="director@devcore.space",
        password_hash=pw_hash,
        role="admin",
    )
    sqlite_session.add(user)
    sqlite_session.commit()
    sqlite_session.refresh(user)

    assert user.id is not None
    assert user.created_at is not None
    assert user.role == "admin"

    public_user = UserRead.model_validate(user).model_dump()
    assert "password_hash" not in public_user
    assert public_user["username"] == "flight_director"
    assert public_user["email"] == "director@devcore.space"


def test_user_unique_username_and_email_constraints(sqlite_session: Session) -> None:
    first = User(
        username="operator1",
        email="op1@devcore.space",
        password_hash=hash_password("StrongPass123!"),
        role="operator",
    )
    sqlite_session.add(first)
    sqlite_session.commit()

    duplicate_username = User(
        username="operator1",
        email="op2@devcore.space",
        password_hash=hash_password("StrongPass123!"),
        role="operator",
    )
    sqlite_session.add(duplicate_username)
    with pytest.raises(IntegrityError):
        sqlite_session.commit()
    sqlite_session.rollback()

    duplicate_email = User(
        username="operator2",
        email="op1@devcore.space",
        password_hash=hash_password("StrongPass123!"),
        role="analyst",
    )
    sqlite_session.add(duplicate_email)
    with pytest.raises(IntegrityError):
        sqlite_session.commit()
    sqlite_session.rollback()


def test_user_role_and_empty_password_constraints(sqlite_session: Session) -> None:
    invalid_role = User(
        username="rogue_user",
        email="rogue@devcore.space",
        password_hash=hash_password("StrongPass123!"),
        role="super_superuser",
    )
    sqlite_session.add(invalid_role)
    with pytest.raises(IntegrityError):
        sqlite_session.commit()
    sqlite_session.rollback()

    with pytest.raises(ValueError):
        hash_password("   ")
