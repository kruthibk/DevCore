"""API v1 router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints import info

api_v1_router = APIRouter()
api_v1_router.include_router(info.router)
