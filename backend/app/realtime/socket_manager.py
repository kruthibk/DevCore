"""Socket.IO ASGI server and event emitters for live telemetry and anomaly streaming."""

from typing import Any, Awaitable, Callable, Dict, Optional

import socketio
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import decode_access_token, normalize_role
from app.db.session import SessionLocal
from app.models.token_revocation import RevokedToken
from app.models.user import User

logger = get_logger(__name__)
settings = get_settings()

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins_list or "*",
    logger=False,
    engineio_logger=False,
)

# Empty socketio_path because FastAPI mounts this sub-app at /socket.io
socket_asgi_app = socketio.ASGIApp(sio, socketio_path="")

_status_provider: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None
_detection_status_provider: Optional[Callable[[], Awaitable[Dict[str, Any]]]] = None


def register_status_provider(provider: Callable[[], Awaitable[Dict[str, Any]]]) -> None:
    """Register an async callback returning current simulator status for new connections."""
    global _status_provider
    _status_provider = provider


def register_detection_status_provider(
    provider: Callable[[], Awaitable[Dict[str, Any]]],
) -> None:
    """Register an async callback returning detection engine status for new connections."""
    global _detection_status_provider
    _detection_status_provider = provider


def _extract_socket_token(environ: dict[str, Any], auth: Optional[Any]) -> Optional[str]:
    if isinstance(auth, dict):
        raw_auth = str(auth.get("token") or "").strip()
        if raw_auth:
            return raw_auth[7:].strip() if raw_auth.lower().startswith("bearer ") else raw_auth

    raw_header = str(environ.get("HTTP_AUTHORIZATION") or "").strip()
    if raw_header.lower().startswith("bearer "):
        return raw_header[7:].strip()

    scope = environ.get("asgi.scope")
    if isinstance(scope, dict):
        for hdr_name, hdr_val in scope.get("headers") or []:
            if isinstance(hdr_name, (bytes, bytearray)) and hdr_name.lower() == b"authorization":
                decoded = hdr_val.decode("utf-8", errors="ignore").strip()
                if decoded.lower().startswith("bearer "):
                    return decoded[7:].strip()
    return None


def _verify_socket_jwt(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    cfg = get_settings()
    try:
        payload = decode_access_token(
            token,
            secret_key=cfg.jwt_secret_key,
            algorithm=cfg.jwt_algorithm,
        )
    except ValueError:
        return None

    jti = str(payload.get("jti") or "")
    username = str(payload.get("sub") or "")
    uid = payload.get("uid")
    if not jti or not username:
        return None

    db = SessionLocal()
    try:
        revoked = db.execute(select(RevokedToken).where(RevokedToken.jti == jti)).scalar_one_or_none()
        if revoked is not None:
            return None
        stmt = (
            select(User).where(User.id == int(uid))
            if isinstance(uid, int)
            else select(User).where(User.username == username)
        )
        user_row = db.execute(stmt).scalar_one_or_none()
        if user_row is None or user_row.username != username or not user_row.is_active:
            return None
        role = normalize_role(user_row.role)
        if role not in ("ADMIN", "OPERATOR"):
            return None
        return username
    except Exception:
        return None
    finally:
        db.close()


async def _emit_initial_status(sid: str) -> None:
    """Emit initial simulation and detection state after the Socket.IO CONNECT ack."""
    # Yield briefly so AsyncServer finishes sending the 40 CONNECT packet and registering `sid`.
    await sio.sleep(0.05)
    if _status_provider is not None:
        try:
            payload = await _status_provider()
            await sio.emit("simulation:status", payload, to=sid)
        except Exception as exc:
            logger.warning(
                "Failed to emit initial simulation status",
                extra={"sid": sid, "error": str(exc)},
            )
    if _detection_status_provider is not None:
        try:
            det_payload = await _detection_status_provider()
            await sio.emit("detection:status", det_payload, to=sid)
        except Exception as exc:
            logger.warning(
                "Failed to emit initial detection status",
                extra={"sid": sid, "error": str(exc)},
            )


@sio.event
async def connect(sid: str, environ: dict[str, Any], auth: Optional[Any] = None) -> None:
    """Authenticate Socket.IO client via JWT and schedule initial simulation & detection status."""
    token = _extract_socket_token(environ, auth)
    username = _verify_socket_jwt(token)
    if not username:
        logger.warning("Rejected unauthenticated Socket.IO client", extra={"sid": sid})
        raise socketio.exceptions.ConnectionRefusedError("Authentication required")

    logger.info("Socket.IO client connected", extra={"sid": sid, "username": username})
    sio.start_background_task(_emit_initial_status, sid)


@sio.event
async def disconnect(sid: str) -> None:
    """Handle dashboard client disconnection cleanly."""
    logger.info("Socket.IO client disconnected", extra={"sid": sid})


async def _safe_emit(event_name: str, payload: Dict[str, Any]) -> None:
    try:
        await sio.emit(event_name, payload)
    except Exception as exc:
        logger.warning(f"Failed to broadcast {event_name}", extra={"error": str(exc)})


async def emit_telemetry_update(payload: Dict[str, Any]) -> None:
    """Broadcast a synthetic telemetry update frame to all connected clients."""
    await _safe_emit("telemetry:update", payload)


async def emit_simulation_status(payload: Dict[str, Any]) -> None:
    """Broadcast simulator lifecycle status updates."""
    await _safe_emit("simulation:status", payload)


async def emit_simulation_fault(payload: Dict[str, Any]) -> None:
    """Broadcast fault-injection state transitions."""
    await _safe_emit("simulation:fault", payload)


async def emit_alert_new(payload: Dict[str, Any]) -> None:
    """Broadcast newly persisted anomaly or integrity alerts."""
    await _safe_emit("alert:new", payload)


async def emit_alert_updated(payload: Dict[str, Any]) -> None:
    """Broadcast updated/acknowledged/resolved alerts."""
    await _safe_emit("alert:updated", payload)


async def emit_detection_status(payload: Dict[str, Any]) -> None:
    """Broadcast detection engine status and per-sensor integrity snapshots."""
    await _safe_emit("detection:status", payload)


async def emit_integrity_issue(payload: Dict[str, Any]) -> None:
    """Broadcast detected cross-signal sensor integrity defects."""
    await _safe_emit("integrity:issue", payload)


async def emit_fault_graph_update(payload: Dict[str, Any]) -> None:
    """Broadcast updated causal fault graph topology and correlations."""
    await _safe_emit("fault_graph:update", payload)


async def emit_correlation_new(payload: Dict[str, Any]) -> None:
    """Broadcast newly persisted alert correlation hypotheses."""
    await _safe_emit("correlation:new", payload)


async def emit_correlation_updated(payload: Dict[str, Any]) -> None:
    """Broadcast updated/acknowledged/dismissed alert correlations."""
    await _safe_emit("correlation:updated", payload)


async def emit_incident_updated(payload: Dict[str, Any]) -> None:
    """Broadcast incident creation, decision linkage, or status transitions."""
    await _safe_emit("incident:updated", payload)
