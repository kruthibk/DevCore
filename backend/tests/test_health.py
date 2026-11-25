"""Tests for /health and /health/db endpoints, CORS, and error handling."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app


def test_health_endpoint_returns_healthy(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "SAT-TRIAGE API"
    assert data["version"] == "0.1.0"
    assert isinstance(data["uptime_seconds"], float)
    assert "timestamp" in data


def test_health_db_endpoint_connected(client: TestClient) -> None:
    response = client.get("/health/db")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["dialect"] == "sqlite"
    assert data["latency_ms"] >= 0
    assert data["error"] is None


def test_health_db_handles_database_failure_gracefully() -> None:
    class FailingSession:
        bind = None

        def execute(self, *_args, **_kwargs):
            raise OperationalError("SELECT 1", {}, Exception("Connection refused"))

    def override_failing_db() -> Generator[FailingSession, None, None]:
        yield FailingSession()

    app.dependency_overrides[get_db] = override_failing_db
    try:
        with TestClient(app) as failing_client:
            response = failing_client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert data["error"] == "Database connection failed or timed out."
    finally:
        app.dependency_overrides.clear()


def test_cors_allows_configured_frontend_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_not_found_returns_structured_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
    assert data["error"]["path"] == "/api/v1/non-existent-route"
    assert data["error"]["request_id"] is not None
