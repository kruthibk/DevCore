"""Schemas for API v1 system info endpoint."""

from datetime import datetime

from pydantic import BaseModel


class TeamMetadata(BaseModel):
    """Hackathon team and problem metadata."""

    name: str
    team_id: str
    problem_statement: str
    domain: str
    event: str


class SystemInfoResponse(BaseModel):
    """Response model for GET /api/v1/info."""

    application: str
    version: str
    api_version: str
    environment: str
    status: str
    team: TeamMetadata
    timestamp: datetime
