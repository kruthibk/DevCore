"""REST endpoints for anomaly detection status and read-only threshold configuration."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.alerts import DetectionConfigResponse, DetectionStatusResponse
from app.services.detection_pipeline import DetectionPipelineService, detection_pipeline

router = APIRouter(prefix="/detection", tags=["Anomaly Detection"])


def get_detection_pipeline() -> DetectionPipelineService:
    """Dependency returning the shared detection pipeline service."""
    return detection_pipeline


@router.get(
    "/status",
    response_model=DetectionStatusResponse,
    summary="Get detection engine status and per-sensor integrity snapshot",
)
def get_detection_status(
    db: Session = Depends(get_db),
    pipeline: DetectionPipelineService = Depends(get_detection_pipeline),
) -> DetectionStatusResponse:
    return pipeline.build_status(db=db)


@router.get(
    "/config",
    response_model=DetectionConfigResponse,
    summary="Get read-only statistical detection thresholds and sensor limits",
)
def get_detection_config(
    pipeline: DetectionPipelineService = Depends(get_detection_pipeline),
) -> DetectionConfigResponse:
    return pipeline.build_config_response()
