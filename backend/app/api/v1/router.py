"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import alerts, copilot, detection, fault_graph, info, simulator, telemetry

api_v1_router = APIRouter()
api_v1_router.include_router(info.router)
api_v1_router.include_router(simulator.router)
api_v1_router.include_router(telemetry.router)
api_v1_router.include_router(alerts.router)
api_v1_router.include_router(detection.router)
api_v1_router.include_router(fault_graph.router)
api_v1_router.include_router(copilot.router)
