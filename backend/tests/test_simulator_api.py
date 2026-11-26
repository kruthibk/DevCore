"""API, Socket.IO emission, persistence, and fault-handling tests for Phase 3."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.endpoints.simulator import get_simulator_service as sim_dep_sim
from app.api.v1.endpoints.telemetry import get_simulator_service as sim_dep_tel
from app.db.base import Base
from app.main import app
from app.services.simulator_service import TelemetrySimulatorService


@pytest.fixture()
def isolated_simulator(tmp_path: Path):
    """Provide an isolated SQLite-backed TelemetrySimulatorService for tests."""
    db_file = tmp_path / "sim_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    service = TelemetrySimulatorService(session_factory=TestingSessionLocal, seed=101)
    service._persist_batch_size = 5  # flush after 1 tick (5 sensors)

    app.dependency_overrides[sim_dep_sim] = lambda: service
    app.dependency_overrides[sim_dep_tel] = lambda: service

    yield service, TestingSessionLocal

    asyncio.run(service.stop_if_running())
    app.dependency_overrides.pop(sim_dep_sim, None)
    app.dependency_overrides.pop(sim_dep_tel, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def test_simulator_start_duplicate_prevention_and_stop(
    client: TestClient,
    admin_headers: dict[str, str],
    isolated_simulator,
) -> None:
    start_res = client.post("/api/v1/simulator/start", json={"interval_seconds": 0.5}, headers=admin_headers)
    assert start_res.status_code == 200
    assert start_res.json()["running"] is True
    assert start_res.json()["interval_seconds"] == 0.5
    assert start_res.json()["data_origin"] == "SYNTHETIC SIMULATION DATA"

    # Duplicate start must be prevented cleanly
    dup_res = client.post("/api/v1/simulator/start", headers=admin_headers)
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "SIMULATOR_ALREADY_RUNNING"

    status_res = client.get("/api/v1/simulator/status", headers=admin_headers)
    assert status_res.status_code == 200
    assert status_res.json()["running"] is True

    stop_res = client.post("/api/v1/simulator/stop", headers=admin_headers)
    assert stop_res.status_code == 200
    assert stop_res.json()["running"] is False


def test_fault_injection_validation_and_clear_endpoints(
    client: TestClient,
    admin_headers: dict[str, str],
    isolated_simulator,
) -> None:
    # Invalid fault scenario rejected
    invalid_res = client.post(
        "/api/v1/simulator/faults",
        json={"fault_type": "solar_flare_fake"},
        headers=admin_headers,
    )
    assert invalid_res.status_code == 422

    # Valid fault activation
    ok_res = client.post(
        "/api/v1/simulator/faults",
        json={"fault_type": "frozen_sensor", "target_sensor": "roll"},
        headers=admin_headers,
    )
    assert ok_res.status_code == 200
    body = ok_res.json()
    assert body["action"] == "activated"
    assert body["active_faults"][0]["fault_type"] == "frozen_sensor"
    assert body["active_faults"][0]["target_sensor"] == "roll"

    # Clear faults
    clear_res = client.post("/api/v1/simulator/faults/clear", headers=admin_headers)
    assert clear_res.status_code == 200
    assert clear_res.json()["action"] == "cleared"
    assert clear_res.json()["active_faults"] == []


def test_telemetry_persistence_latest_and_history_filters(
    client: TestClient,
    isolated_simulator,
) -> None:
    service, session_factory = isolated_simulator

    # Override get_db to point at the same SQLite DB as isolated_simulator
    from app.db.session import get_db
    from tests.conftest import make_test_auth_headers

    def override_db():
        db: Session = session_factory()
        try:
            yield db
        finally:
            db.close()

    with session_factory() as auth_db:
        headers = make_test_auth_headers(auth_db, username="sim_op", role="OPERATOR")

    app.dependency_overrides[get_db] = override_db
    try:
        asyncio.run(service.step_once())
        asyncio.run(service.step_once())

        status_data = client.get("/api/v1/simulator/status", headers=headers).json()
        assert status_data["generated_count"] == 10
        assert status_data["streamed_count"] == 10
        assert status_data["persisted_count"] == 10

        latest_res = client.get("/api/v1/telemetry/latest", headers=headers)
        assert latest_res.status_code == 200
        latest_json = latest_res.json()
        assert latest_json["data_origin"] == "SYNTHETIC SIMULATION DATA"
        assert set(latest_json["readings"].keys()) == {
            "battery_voltage",
            "temperature",
            "roll",
            "pitch",
            "yaw",
        }

        # Filter by sensor_name and bounded pagination
        hist_res = client.get(
            "/api/v1/telemetry/history",
            params={"sensor_name": "battery_voltage", "limit": 1, "offset": 0},
            headers=headers,
        )
        assert hist_res.status_code == 200
        hist_json = hist_res.json()
        assert hist_json["total"] == 2
        assert len(hist_json["items"]) == 1
        assert hist_json["items"][0]["sensor_name"] == "battery_voltage"

        # Future time window returns 0 items
        future_start = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        empty_hist = client.get(
            "/api/v1/telemetry/history",
            params={"start_time": future_start},
            headers=headers,
        )
        assert empty_hist.status_code == 200
        assert empty_hist.json()["total"] == 0
        assert empty_hist.json()["items"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_socketio_event_emission_on_tick_and_fault(
    monkeypatch: pytest.MonkeyPatch,
    isolated_simulator,
) -> None:
    service, _ = isolated_simulator

    emit_update = AsyncMock()
    emit_fault = AsyncMock()
    emit_status = AsyncMock()

    monkeypatch.setattr("app.services.simulator_service.emit_telemetry_update", emit_update)
    monkeypatch.setattr("app.services.simulator_service.emit_simulation_fault", emit_fault)
    monkeypatch.setattr("app.services.simulator_service.emit_simulation_status", emit_status)

    asyncio.run(service.step_once())
    assert emit_update.await_count == 1
    payload = emit_update.await_args.args[0]
    assert payload["satellite_id"] == "SAT-01"
    assert payload["data_origin"] == "SYNTHETIC SIMULATION DATA"
    assert len(payload["readings"]) == 5

    asyncio.run(service.inject_fault("temperature_spike"))
    assert emit_fault.await_count == 1
    assert emit_status.await_count == 1
    assert emit_fault.await_args.args[0]["fault_type"] == "temperature_spike"


def test_simulator_handles_database_persistence_failure_gracefully() -> None:
    def failing_session_factory():
        raise RuntimeError("Simulated PostgreSQL outage")

    service = TelemetrySimulatorService(session_factory=failing_session_factory, seed=55)
    service._persist_batch_size = 5

    samples = asyncio.run(service.step_once())
    assert len(samples) == 5
    assert service.generated_count == 5
    assert service.streamed_count == 5
    # Must NOT falsely claim persisted when DB failed
    assert service.persisted_count == 0
    assert service.failed_persist_batches == 1
    assert "Simulated PostgreSQL outage" in (service.last_persistence_error or "")
