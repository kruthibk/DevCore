"""Security helpers for password hashing, role normalization, and HMAC-SHA256 JWT tokens."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

import bcrypt

RbacRole = Literal["ADMIN", "OPERATOR", "VIEWER"]

_ROLE_MAP: Dict[str, RbacRole] = {
    "admin": "ADMIN",
    "operator": "OPERATOR",
    "viewer": "VIEWER",
    "analyst": "VIEWER",
}


def normalize_role(raw_role: Optional[str]) -> Optional[RbacRole]:
    """Normalize stored role strings into ADMIN, OPERATOR, or VIEWER."""
    if not raw_role or not raw_role.strip():
        return None
    return _ROLE_MAP.get(raw_role.strip().lower())


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


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def create_access_token(
    subject: str,
    role: str,
    secret_key: str,
    user_id: Optional[int] = None,
    expires_seconds: int = 28800,
    algorithm: str = "HS256",
) -> str:
    """Create an HMAC-SHA256 signed JWT bearer token with unique jti and expiration."""
    if algorithm.upper() != "HS256":
        raise ValueError(f"Unsupported JWT algorithm: {algorithm}")
    normalized = normalize_role(role) or "OPERATOR"
    header = _b64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8")
    )
    now = int(time.time())
    payload_dict: Dict[str, Any] = {
        "sub": subject,
        "role": normalized,
        "jti": uuid4().hex,
        "iat": now,
        "exp": now + expires_seconds,
    }
    if user_id is not None:
        payload_dict["uid"] = user_id
    payload = _b64url_encode(json.dumps(payload_dict, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = _b64url_encode(hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> Dict[str, Any]:
    """Verify JWT signature, header algorithm, claims, and expiration."""
    if algorithm.upper() != "HS256":
        raise ValueError("Unsupported JWT algorithm.")
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format.")
    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Malformed token header.") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ValueError("Unexpected JWT signing algorithm.")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = _b64url_encode(
        hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sig_b64, expected_sig):
        raise ValueError("Invalid token signature.")
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Malformed token payload.") from exc
    if not isinstance(payload, dict) or not payload.get("sub") or not payload.get("jti"):
        raise ValueError("Token missing required claims.")
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or time.time() >= float(exp):
        raise ValueError("Token expired.")
    return payload
