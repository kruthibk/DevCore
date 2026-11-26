"""REST endpoints for querying latest and historical synthetic telemetry."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.rbac import ActorContext, require_roles
from app.db.session import get_db
from app.schemas.telemetry import (
    SensorName,
    TelemetryHistoryResponse,
    TelemetryLatestResponse,
)
from app.services.simulator_service import TelemetrySimulatorService, simulator_service

router = APIRouter(prefix="/telemetry", tags=["Telemetry Data"])


def get_simulator_service() -> TelemetrySimulatorService:
    """Dependency returning the shared telemetry simulator service."""
    return simulator_service


@router.get(
    "/latest",
    response_model=TelemetryLatestResponse,
    summary="Get latest synthetic sensor readings",
)
def get_latest_telemetry(
    satellite_id: str = Query(default="SAT-01", min_length=2, max_length=32),
    db: Session = Depends(get_db),
    service: TelemetrySimulatorService = Depends(get_simulator_service),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> TelemetryLatestResponse:
    return service.get_latest_readings(db=db, satellite_id=satellite_id)


@router.get(
    "/history",
    response_model=TelemetryHistoryResponse,
    summary="Query persisted historical telemetry with filters and pagination",
)
def get_telemetry_history(
    satellite_id: str = Query(default="SAT-01", min_length=2, max_length=32),
    sensor_name: Optional[SensorName] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    service: TelemetrySimulatorService = Depends(get_simulator_service),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> TelemetryHistoryResponse:
    items, total = service.get_history(
        db=db,
        satellite_id=satellite_id,
        sensor_name=sensor_name,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return TelemetryHistoryResponse(
        satellite_id=satellite_id,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )
