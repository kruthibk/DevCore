"""REST endpoints for the hybrid causal fault graph and alert correlations."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.fault_graph_config import DEFAULT_CORRELATION_WINDOW_SECONDS
from app.core.rbac import ActorContext, require_roles
from app.db.session import get_db
from app.realtime.socket_manager import emit_correlation_updated, emit_fault_graph_update
from app.schemas.fault_graph import (
    CorrelationDetailResponse,
    CorrelationListResponse,
    CorrelationRead,
    CorrelationStatus,
    FaultGraphResponse,
)
from app.services.correlation_engine import CorrelationService

router = APIRouter(prefix="/fault-graph", tags=["Fault Graph & Correlation"])


@router.get(
    "",
    response_model=FaultGraphResponse,
    summary="Get subsystem dependency graph, alert nodes, and active correlations",
)
def get_fault_graph(
    satellite_id: str = Query(default="SAT-01", max_length=32),
    window_seconds: float = Query(
        default=DEFAULT_CORRELATION_WINDOW_SECONDS,
        ge=10.0,
        le=86400.0,
    ),
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> FaultGraphResponse:
    return CorrelationService.build_fault_graph(
        db=db,
        satellite_id=satellite_id,
        window_seconds=window_seconds,
    )


@router.get(
    "/correlations",
    response_model=CorrelationListResponse,
    summary="List persisted alert correlation hypotheses",
)
def list_correlations(
    satellite_id: Optional[str] = Query(default=None, max_length=32),
    status: Optional[CorrelationStatus] = Query(default=None),
    suspected_subsystem: Optional[str] = Query(default=None, max_length=32),
    window_seconds: Optional[float] = Query(default=None, ge=10.0, le=86400.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> CorrelationListResponse:
    items, total, summary = CorrelationService.list_correlations(
        db=db,
        satellite_id=satellite_id,
        status_filter=status,
        suspected_subsystem=suspected_subsystem,
        window_seconds=window_seconds,
        limit=limit,
        offset=offset,
    )
    return CorrelationListResponse(
        total=total,
        limit=limit,
        offset=offset,
        summary=summary,
        items=items,
    )


@router.get(
    "/correlations/{correlation_id}",
    response_model=CorrelationDetailResponse,
    summary="Get full correlation details, linked alerts, and evidence",
)
def get_correlation(
    correlation_id: str,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> CorrelationDetailResponse:
    return CorrelationService.get_correlation_detail(db=db, correlation_id=correlation_id)


@router.post(
    "/correlations/{correlation_id}/acknowledge",
    response_model=CorrelationRead,
    summary="Acknowledge a correlation hypothesis",
)
async def acknowledge_correlation(
    correlation_id: str,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> CorrelationRead:
    updated = CorrelationService.acknowledge_correlation(db=db, correlation_id=correlation_id)
    await emit_correlation_updated(updated.model_dump(mode="json"))
    graph_snapshot = CorrelationService.build_fault_graph(db=db, satellite_id=updated.satellite_id)
    await emit_fault_graph_update(graph_snapshot.model_dump(mode="json"))
    return updated


@router.post(
    "/correlations/{correlation_id}/dismiss",
    response_model=CorrelationRead,
    summary="Dismiss a correlation hypothesis",
)
async def dismiss_correlation(
    correlation_id: str,
    db: Session = Depends(get_db),
    _: ActorContext = Depends(require_roles("OPERATOR", "ADMIN")),
) -> CorrelationRead:
    updated = CorrelationService.dismiss_correlation(db=db, correlation_id=correlation_id)
    await emit_correlation_updated(updated.model_dump(mode="json"))
    graph_snapshot = CorrelationService.build_fault_graph(db=db, satellite_id=updated.satellite_id)
    await emit_fault_graph_update(graph_snapshot.model_dump(mode="json"))
    return updated
