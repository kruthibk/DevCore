"""Socket.IO ASGI server and event emitters for live telemetry and anomaly streaming."""

from typing import Any, Awaitable, Callable, Dict, Optional

import socketio

from app.core.config import get_settings
from app.core.logging import get_logger

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


@sio.event
async def connect(sid: str, _environ: dict[str, Any]) -> None:
    """Handle dashboard client connection and send initial simulation & detection status."""
    logger.info("Socket.IO client connected", extra={"sid": sid})
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
