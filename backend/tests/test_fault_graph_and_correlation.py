"""Tests for Phase 5 hybrid causal fault graph, alert correlation, persistence, and Socket.IO."""

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
from app.core.detection_config import DetectionConfig
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import alert as _alert_model  # noqa: F401
from app.models import correlation as _corr_model  # noqa: F401
from app.schemas.alerts import AlertRead
from app.schemas.telemetry import SENSOR_UNITS, TelemetrySampleSchema
from app.services.correlation_engine import (
    CorrelationService,
    evaluate_correlations_for_alerts,
)
from app.services.detection_pipeline import DetectionPipelineService


def _make_alert(
    alert_id: str,
    sensor_name: str,
    alert_type: str,
    severity: str,
    ts: datetime,
    satellite_id: str = "SAT-01",
) -> AlertRead:
    return AlertRead(
        id=1,
        alert_id=alert_id,
        satellite_id=satellite_id,
        sensor_name=sensor_name,  # type: ignore[arg-type]
        alert_type=alert_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        status="ACTIVE",
        title=f"{alert_type} on {sensor_name}",
        description=f"Observed {alert_type} on {sensor_name}.",
        observed_value=24.0,
        expected_range="nominal",
        z_score=4.1 if alert_type == "STATISTICAL_ANOMALY" else None,
        reason_code="TEST_CODE",
        evidence={"unit": SENSOR_UNITS.get(sensor_name, "")},
        first_detected_at=ts,
        last_detected_at=ts,
        occurrence_count=1,
        created_at=ts,
        updated_at=ts,
    )


def _sample(sensor: str, value, ts: datetime) -> TelemetrySampleSchema:
    return TelemetrySampleSchema(
        satellite_id="SAT-01",
        sensor_name=sensor,  # type: ignore[arg-type]
        sensor_value=value,
        unit=SENSOR_UNITS[sensor],
        timestamp=ts,
        quality_status="NOMINAL",
    )


def test_related_alerts_are_grouped_into_causal_hypotheses() -> None:
    now = datetime(2026, 11, 26, 2, 0, 0, tzinfo=timezone.utc)

    # Coupled EPS + Thermal alerts within 10s
    coupled = [
        _make_alert("ALT-1", "battery_voltage", "ENGINEERING_LIMIT", "CRITICAL", now - timedelta(seconds=8)),
        _make_alert("ALT-2", "temperature", "STATISTICAL_ANOMALY", "CRITICAL", now),
    ]
    corrs = evaluate_correlations_for_alerts(coupled, satellite_id="SAT-01", window_seconds=120.0, reference_time=now)
    assert len(corrs) == 1
    assert corrs[0].rule_code == "EPS_THERMAL_COUPLED_FAULT"
    assert corrs[0].suspected_subsystem == "EPS"
    assert set(corrs[0].related_alert_ids) == {"ALT-1", "ALT-2"}
    assert len(corrs[0].supporting_evidence) >= 3
    assert len(corrs[0].contradicting_evidence) >= 1
    assert 0.15 <= corrs[0].confidence_score <= 0.92
    assert "not a calibrated probability" in corrs[0].confidence_explanation

    # Multi-sensor integrity issues -> OBC rule
    obc_alerts = [
        _make_alert("ALT-3", "roll", "SENSOR_FROZEN", "WARNING", now - timedelta(seconds=5)),
        _make_alert("ALT-4", "yaw", "SENSOR_MISSING", "WARNING", now),
    ]
    obc_corrs = evaluate_correlations_for_alerts(obc_alerts, satellite_id="SAT-01", window_seconds=120.0, reference_time=now)
    assert len(obc_corrs) == 1
    assert obc_corrs[0].rule_code == "OBC_MULTI_CHANNEL_INTEGRITY"
    assert obc_corrs[0].suspected_subsystem == "OBC"

    # ADCS/EPS solar coupling must match pitch or yaw even without roll
    pitch_eps_alerts = [
        _make_alert("ALT-5", "battery_voltage", "ENGINEERING_LIMIT", "WARNING", now - timedelta(seconds=6)),
        _make_alert("ALT-6", "pitch", "STATISTICAL_ANOMALY", "WARNING", now),
    ]
    adcs_eps = evaluate_correlations_for_alerts(
        pitch_eps_alerts, satellite_id="SAT-01", window_seconds=120.0, reference_time=now
    )
    assert len(adcs_eps) == 1
    assert adcs_eps[0].rule_code == "ADCS_EPS_SOLAR_COUPLING"
    assert adcs_eps[0].suspected_subsystem == "ADCS"
    from app.core.fault_graph_config import CAUSAL_RULES

    solar_rule = next(r for r in CAUSAL_RULES if r.rule_code == "ADCS_EPS_SOLAR_COUPLING")
    assert set(solar_rule.required_sensors) == {"battery_voltage", "roll", "pitch", "yaw"}


def test_unrelated_and_out_of_window_alerts_are_not_grouped() -> None:
    now = datetime(2026, 11, 26, 2, 0, 0, tzinfo=timezone.utc)

    # Different satellites -> never grouped
    diff_sat = [
        _make_alert("ALT-S1", "battery_voltage", "ENGINEERING_LIMIT", "CRITICAL", now, satellite_id="SAT-01"),
        _make_alert("ALT-S2", "temperature", "ENGINEERING_LIMIT", "CRITICAL", now, satellite_id="SAT-02"),
    ]
    assert evaluate_correlations_for_alerts(diff_sat, satellite_id="SAT-01", window_seconds=120.0, reference_time=now) == []

    # Isolated single physical battery alert + isolated single yaw missing integrity alert -> not grouped together
    unrelated = [
        _make_alert("ALT-U1", "battery_voltage", "ENGINEERING_LIMIT", "WARNING", now),
        _make_alert("ALT-U2", "yaw", "SENSOR_MISSING", "WARNING", now),
    ]
    assert evaluate_correlations_for_alerts(unrelated, satellite_id="SAT-01", window_seconds=120.0, reference_time=now) == []

    # Outside time window (180s apart > 60s window) -> not grouped
    stale_pair = [
        _make_alert("ALT-W1", "battery_voltage", "ENGINEERING_LIMIT", "CRITICAL", now - timedelta(seconds=180)),
        _make_alert("ALT-W2", "temperature", "ENGINEERING_LIMIT", "CRITICAL", now),
    ]
    assert evaluate_correlations_for_alerts(stale_pair, satellite_id="SAT-01", window_seconds=60.0, reference_time=now) == []


def test_correlation_persistence_apis_lifecycle_and_socketio_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_file = tmp_path / "fault_graph_test.db"
    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    pipeline = DetectionPipelineService(
        session_factory=TestingSessionLocal,
        config=DetectionConfig(dedup_cooldown_seconds=0.0, auto_resolve_on_recovery=False),
    )

    emit_corr_new = AsyncMock()
    emit_corr_upd = AsyncMock()
    emit_graph_upd = AsyncMock()

    monkeypatch.setattr("app.services.detection_pipeline.emit_correlation_new", emit_corr_new)
    monkeypatch.setattr("app.services.detection_pipeline.emit_correlation_updated", emit_corr_upd)
    monkeypatch.setattr("app.services.detection_pipeline.emit_fault_graph_update", emit_graph_upd)
    monkeypatch.setattr("app.api.v1.endpoints.fault_graph.emit_correlation_updated", emit_corr_upd)
    monkeypatch.setattr("app.api.v1.endpoints.fault_graph.emit_fault_graph_update", emit_graph_upd)

    def override_db():
        db: Session = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[alerts_dep_pipeline] = lambda: pipeline
    app.dependency_overrides[det_dep_pipeline] = lambda: pipeline

    with TestingSessionLocal() as auth_db:
        from tests.conftest import make_test_auth_headers

        auth_headers = make_test_auth_headers(auth_db, username="fg_op", role="OPERATOR")

    try:
        with TestClient(app) as client:
            base_ts = datetime.now(timezone.utc) - timedelta(seconds=20)
            # Warm up 10 nominal samples on battery_voltage & temperature
            for i in range(10):
                ts = base_ts + timedelta(seconds=i)
                asyncio.run(
                    pipeline.process_batch(
                        [
                            _sample("battery_voltage", 28.0 + (0.1 if i % 2 == 0 else -0.1), ts),
                            _sample("temperature", 22.5 + (0.2 if i % 2 == 0 else -0.2), ts),
                        ],
                        simulator_running=True,
                    )
                )

            # Inject coupled battery drop + temperature spike
            fault_ts = datetime.now(timezone.utc)
            asyncio.run(
                pipeline.process_batch(
                    [
                        _sample("battery_voltage", 20.8, fault_ts),
                        _sample("temperature", 58.0, fault_ts),
                    ],
                    simulator_running=True,
                )
            )

            assert emit_corr_new.await_count >= 1
            assert emit_graph_upd.await_count >= 1

            # GET /api/v1/fault-graph
            graph_res = client.get(
                "/api/v1/fault-graph",
                params={"satellite_id": "SAT-01", "window_seconds": 120},
                headers=auth_headers,
            )
            assert graph_res.status_code == 200
            graph_data = graph_res.json()
            assert len(graph_data["correlations"]) >= 1
            node_types = {n["node_type"] for n in graph_data["nodes"]}
            assert {"subsystem", "sensor", "alert"}.issubset(node_types)
            subsystems = {n["subsystem"] for n in graph_data["nodes"] if n["node_type"] == "subsystem"}
            assert {"EPS", "THERMAL", "ADCS", "OBC", "SENSORS"} == subsystems

            # GET /api/v1/fault-graph/correlations with time window filter
            list_res = client.get(
                "/api/v1/fault-graph/correlations",
                params={"window_seconds": 120},
                headers=auth_headers,
            )
            assert list_res.status_code == 200
            list_data = list_res.json()
            assert list_data["total"] >= 1
            corr_id = list_data["items"][0]["correlation_id"]

            # GET /api/v1/fault-graph/correlations/{id}
            detail_res = client.get(
                f"/api/v1/fault-graph/correlations/{corr_id}",
                headers=auth_headers,
            )
            assert detail_res.status_code == 200
            detail_json = detail_res.json()
            assert len(detail_json["related_alerts"]) >= 2
            assert len(detail_json["supporting_evidence"]) >= 1

            # Acknowledge
            ack_res = client.post(
                f"/api/v1/fault-graph/correlations/{corr_id}/acknowledge",
                headers=auth_headers,
            )
            assert ack_res.status_code == 200
            assert ack_res.json()["status"] == "ACKNOWLEDGED"

            # Dismiss
            dis_res = client.post(
                f"/api/v1/fault-graph/correlations/{corr_id}/dismiss",
                headers=auth_headers,
            )
            assert dis_res.status_code == 200
            assert dis_res.json()["status"] == "DISMISSED"

            # Dismissed -> Acknowledge rejected cleanly
            bad_ack = client.post(
                f"/api/v1/fault-graph/correlations/{corr_id}/acknowledge",
                headers=auth_headers,
            )
            assert bad_ack.status_code == 409

            # Emitted update events on ack/dismiss
            assert emit_corr_upd.await_count >= 2
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
