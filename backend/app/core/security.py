"""Security helpers for password hashing and verification."""

import bcrypt


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt with an automatic random salt."""
    if not plain_password or not plain_password.strip():
        raise ValueError("Password must not be empty.")
    password_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not plain_password or not password_hash:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
