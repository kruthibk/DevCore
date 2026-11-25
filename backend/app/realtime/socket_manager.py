"""Socket.IO ASGI server and event emitters for live telemetry streaming."""

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


def register_status_provider(provider: Callable[[], Awaitable[Dict[str, Any]]]) -> None:
    """Register an async callback returning current simulator status for new connections."""
    global _status_provider
    _status_provider = provider


@sio.event
async def connect(sid: str, _environ: dict[str, Any]) -> None:
    """Handle dashboard client connection and send initial simulation status."""
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


@sio.event
async def disconnect(sid: str) -> None:
    """Handle dashboard client disconnection cleanly."""
    logger.info("Socket.IO client disconnected", extra={"sid": sid})


async def emit_telemetry_update(payload: Dict[str, Any]) -> None:
    """Broadcast a synthetic telemetry update frame to all connected clients."""
    try:
        await sio.emit("telemetry:update", payload)
    except Exception as exc:
        logger.warning("Failed to broadcast telemetry:update", extra={"error": str(exc)})


async def emit_simulation_status(payload: Dict[str, Any]) -> None:
    """Broadcast simulator lifecycle status updates."""
    try:
        await sio.emit("simulation:status", payload)
    except Exception as exc:
        logger.warning("Failed to broadcast simulation:status", extra={"error": str(exc)})


async def emit_simulation_fault(payload: Dict[str, Any]) -> None:
    """Broadcast fault-injection state transitions."""
    try:
        await sio.emit("simulation:fault", payload)
    except Exception as exc:
        logger.warning("Failed to broadcast simulation:fault", extra={"error": str(exc)})
