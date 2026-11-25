"""Initial User ORM model with strict constraints."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ALLOWED_USER_ROLES = ("operator", "analyst", "admin")


class User(Base):
    """Represents a SAT-TRIAGE platform user."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(username)) >= 3", name="ck_users_username_min_len"),
        CheckConstraint("length(trim(email)) >= 5", name="ck_users_email_min_len"),
        CheckConstraint("length(password_hash) > 0", name="ck_users_password_hash_non_empty"),
        CheckConstraint(
            "role IN ('operator', 'analyst', 'admin')",
            name="ck_users_valid_role",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="operator", server_default="operator")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role!r}>"
