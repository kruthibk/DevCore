"""FastAPI application entrypoint for SAT-TRIAGE."""

from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db
from app.db.session import engine, get_db
from app.realtime.socket_manager import socket_asgi_app
from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.services.health_service import check_database_health, get_service_health
from app.services.simulator_service import simulator_service

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize database schema, RBAC demo users, and release resources cleanly on shutdown."""
    logger.info(
        "Starting SAT-TRIAGE backend",
        extra={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
    )
    init_db(engine)
    yield
    await simulator_service.stop_if_running()
    engine.dispose()
    logger.info("SAT-TRIAGE backend shut down cleanly")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="SAT-TRIAGE — Satellite Telemetry Anomaly Triage Copilot Backend API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        started = perf_counter()

        response = await call_next(request)

        duration_ms = round((perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "HTTP request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    register_exception_handlers(application)

    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Check backend service health",
    )
    async def health(app_settings: Settings = Depends(get_settings)) -> HealthResponse:
        return get_service_health(app_settings)

    @application.get(
        "/health/db",
        response_model=DatabaseHealthResponse,
        tags=["Health"],
        summary="Check PostgreSQL database connectivity",
        responses={
            status.HTTP_503_SERVICE_UNAVAILABLE: {
                "model": DatabaseHealthResponse,
                "description": "Database is unreachable or unhealthy",
            }
        },
    )
    def health_db(db: Session = Depends(get_db)) -> JSONResponse:
        payload, is_healthy = check_database_health(db)
        http_status = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(status_code=http_status, content=payload.model_dump(mode="json"))

    application.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    application.mount("/socket.io", socket_asgi_app)

    return application


app = create_app()
