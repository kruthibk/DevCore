"""Tests for alert persistence, deduplication, REST APIs, DB failure handling, and Socket.IO."""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.endpoints.alerts import get_detection_pipeline as alerts_dep_pipeline
from app.api.v1.endpoints.detection import get_detection_pipeline as det_dep_pipeline
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import alert as _alert_model  # noqa: F401
from app.schemas.telemetry import SENSOR_UNITS, TelemetrySampleSchema
from app.services.detection_pipeline import DetectionPipelineService


@pytest.fixture()
def isolated_pipeline(tmp_path: Path):
    """Provide an isolated SQLite-backed DetectionPipelineService and wired TestClient."""
    db_file = tmp_path / "alerts_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    pipeline = DetectionPipelineService(session_factory=TestingSessionLocal)

    def override_db():
        db: Session = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[alerts_dep_pipeline] = lambda: pipeline
    app.dependency_overrides[det_dep_pipeline] = lambda: pipeline

    with TestClient(app) as test_client:
        yield test_client, pipeline, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def _sample(sensor: str, value, ts: datetime) -> TelemetrySampleSchema:
    return TelemetrySampleSchema(
        satellite_id="SAT-01",
        sensor_name=sensor,  # type: ignore[arg-type]
        sensor_value=value,
        unit=SENSOR_UNITS[sensor],
        timestamp=ts,
        quality_status="NOMINAL",
    )


def test_alert_persistence_deduplication_occurrence_and_lifecycle(
    isolated_pipeline,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, pipeline, _ = isolated_pipeline

    emit_new = AsyncMock()
    emit_updated = AsyncMock()
    emit_det_status = AsyncMock()
    emit_integrity = AsyncMock()

    monkeypatch.setattr("app.services.detection_pipeline.emit_alert_new", emit_new)
    monkeypatch.setattr("app.services.detection_pipeline.emit_alert_updated", emit_updated)
    monkeypatch.setattr("app.services.detection_pipeline.emit_detection_status", emit_det_status)
    monkeypatch.setattr("app.services.detection_pipeline.emit_integrity_issue", emit_integrity)
    monkeypatch.setattr("app.api.v1.endpoints.alerts.emit_alert_updated", emit_updated)
    monkeypatch.setattr("app.api.v1.endpoints.alerts.emit_detection_status", emit_det_status)

    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Missing sensor triggers 1 new SENSOR_MISSING alert
    created1, updated1, integrity1 = asyncio.run(
        pipeline.process_batch([_sample("yaw", None, base_ts)], simulator_running=True)
    )
    assert len(created1) == 1
    assert len(updated1) == 0
    assert len(integrity1) == 1
    assert emit_new.await_count == 1
    assert emit_integrity.await_count == 1
    alert_id = created1[0].alert_id

    # 2. Repeated missing sensor after cooldown suppresses duplicate creation and increments occurrence_count
    created2, updated2, _ = asyncio.run(
        pipeline.process_batch(
            [_sample("yaw", None, base_ts + timedelta(seconds=12))],
            simulator_running=True,
        )
    )
    assert len(created2) == 0
    assert len(updated2) == 1
    assert updated2[0].alert_id == alert_id
    assert updated2[0].occurrence_count == 2
    assert emit_updated.await_count == 1

    # 3. Verify GET /api/v1/alerts filtering and pagination
    list_res = client.get("/api/v1/alerts", params={"alert_type": "SENSOR_MISSING", "limit": 10, "offset": 0})
    assert list_res.status_code == 200
    list_json = list_res.json()
    assert list_json["total"] == 1
    assert list_json["summary"]["active"] == 1
    assert list_json["items"][0]["occurrence_count"] == 2

    # 4. Verify GET /api/v1/alerts/{alert_id}
    detail_res = client.get(f"/api/v1/alerts/{alert_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["reason_code"] == "SENSOR_VALUE_MISSING"

    # 5. Acknowledge action
    ack_res = client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"
    assert ack_res.json()["acknowledged_at"] is not None

    # 6. Resolve action
    resolve_res = client.post(f"/api/v1/alerts/{alert_id}/resolve")
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"
    assert resolve_res.json()["resolved_at"] is not None

    # Cannot re-acknowledge a resolved alert
    bad_ack = client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert bad_ack.status_code == 409

    # 7. Verify detection status & config endpoints
    det_status = client.get("/api/v1/detection/status")
    assert det_status.status_code == 200
    assert det_status.json()["processed_sample_count"] == 2
    assert det_status.json()["active_alert_count"] == 0

    det_cfg = client.get("/api/v1/detection/config")
    assert det_cfg.status_code == 200
    assert "battery_voltage" in det_cfg.json()["sensor_limits"]


def test_detection_pipeline_handles_database_failure_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_session():
        raise RuntimeError("Simulated PostgreSQL failure during alert insert")

    pipeline = DetectionPipelineService(session_factory=failing_session)
    emit_new = AsyncMock()
    monkeypatch.setattr("app.services.detection_pipeline.emit_alert_new", emit_new)

    ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)
    created, updated, integrity = asyncio.run(
        pipeline.process_batch([_sample("temperature", None, ts)], simulator_running=True)
    )

    # Must detect integrity issue in memory, fail DB persistence safely, and NOT claim alert persisted
    assert len(integrity) == 1
    assert created == []
    assert updated == []
    assert pipeline.persisted_alerts_count == 0
    assert pipeline.failed_persist_count == 1
    assert "Simulated PostgreSQL failure" in (pipeline.last_persistence_error or "")
    assert emit_new.await_count == 0
