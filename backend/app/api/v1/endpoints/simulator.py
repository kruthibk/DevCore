"""REST endpoints for controlling the synthetic telemetry simulator."""

from typing import Optional

from fastapi import APIRouter, Body, Depends

from app.core.rbac import ActorContext, require_roles
from app.schemas.telemetry import (
    FaultActionResponse,
    FaultInjectRequest,
    SimulatorStartRequest,
    SimulatorStatusResponse,
)
from app.services.simulator_service import TelemetrySimulatorService, simulator_service

router = APIRouter(prefix="/simulator", tags=["Telemetry Simulator"])


def get_simulator_service() -> TelemetrySimulatorService:
    """Dependency returning the shared telemetry simulator service."""
    return simulator_service


@router.post(
    "/start",
    response_model=SimulatorStatusResponse,
    summary="Start synthetic telemetry generation",
)
async def start_simulator(
    payload: Optional[SimulatorStartRequest] = Body(default=None),
    service: TelemetrySimulatorService = Depends(get_simulator_service),
    _: ActorContext = Depends(require_roles("ADMIN")),
) -> SimulatorStatusResponse:
    interval = payload.interval_seconds if payload else None
    return await service.start(interval_seconds=interval)


@router.post(
    "/stop",
    response_model=SimulatorStatusResponse,
    summary="Stop synthetic telemetry generation gracefully",
)
async def stop_simulator(
    service: TelemetrySimulatorService = Depends(get_simulator_service),
    _: ActorContext = Depends(require_roles("ADMIN")),
) -> SimulatorStatusResponse:
    return await service.stop()


@router.get(
    "/status",
    response_model=SimulatorStatusResponse,
    summary="Get simulator running state and active faults",
)
async def get_simulator_status(
    service: TelemetrySimulatorService = Depends(get_simulator_service),
) -> SimulatorStatusResponse:
    return service.build_status()


@router.post(
    "/faults",
    response_model=FaultActionResponse,
    summary="Activate a synthetic fault scenario",
)
async def inject_fault(
    payload: FaultInjectRequest,
    service: TelemetrySimulatorService = Depends(get_simulator_service),
    _: ActorContext = Depends(require_roles("ADMIN")),
) -> FaultActionResponse:
    return await service.inject_fault(
        fault_type=payload.fault_type,
        target_sensor=payload.target_sensor,
    )


@router.post(
    "/faults/clear",
    response_model=FaultActionResponse,
    summary="Clear all active synthetic fault scenarios",
)
async def clear_faults(
    service: TelemetrySimulatorService = Depends(get_simulator_service),
    _: ActorContext = Depends(require_roles("ADMIN")),
) -> FaultActionResponse:
    return await service.clear_faults()
