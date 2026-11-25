"""API v1 system info endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.info import SystemInfoResponse, TeamMetadata

router = APIRouter(tags=["System Info"])


@router.get("/info", response_model=SystemInfoResponse, summary="Get SAT-TRIAGE API v1 metadata")
async def get_system_info(settings: Settings = Depends(get_settings)) -> SystemInfoResponse:
    """Return application metadata, API version, and team information."""
    return SystemInfoResponse(
        application="SAT-TRIAGE",
        version=settings.app_version,
        api_version="v1",
        environment=settings.environment,
        status="operational",
        team=TeamMetadata(
            name="DevCore",
            team_id="AV26-BF34B6F9D2",
            problem_statement="11 — Satellite Telemetry Anomaly Triage Copilot",
            domain="Full Stack Web Development",
            event="AVISHKAR'26",
        ),
        timestamp=datetime.now(timezone.utc),
    )
