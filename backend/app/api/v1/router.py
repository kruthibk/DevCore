"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import info, simulator, telemetry

api_v1_router = APIRouter()
api_v1_router.include_router(info.router)
api_v1_router.include_router(simulator.router)
api_v1_router.include_router(telemetry.router)
