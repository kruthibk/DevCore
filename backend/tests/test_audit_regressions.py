"""Regression tests for the Phase 4 detection correctness audit."""

import asyncio
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.detection_config import DetectionConfig
from app.db.base import Base
from app.models import alert as _alert_model  # noqa: F401
from app.schemas.telemetry import SENSOR_UNITS, TelemetrySampleSchema
from app.services.alert_service import AlertCandidate, AlertService
from app.services.anomaly_detector import StatisticalAnomalyDetector, compute_z_score_stats
from app.services.detection_pipeline import DetectionPipelineService
from app.services.sensor_integrity_service import SensorIntegrityService


def _sample(
    sensor: str,
    value,
    ts: datetime,
    satellite_id: str = "SAT-01",
    quality_status: str = "NOMINAL",
) -> TelemetrySampleSchema:
    return TelemetrySampleSchema(
        satellite_id=satellite_id,
        sensor_name=sensor,  # type: ignore[arg-type]
        sensor_value=value,
        unit=SENSOR_UNITS[sensor],
        timestamp=ts,
        quality_status=quality_status,  # type: ignore[arg-type]
    )


def test_authoritative_z_score_matches_evidence_and_direction_positive_negative_near_zero() -> None:
    baseline = [28.0, 28.2, 27.8, 28.1, 27.9, 28.15, 27.85, 28.05, 27.95, 28.1]

    # Positive deviation -> ABOVE
    pos = compute_z_score_stats(
        observed_value=29.2,
        baseline_values=baseline,
        min_baseline_samples=8,
        min_meaningful_std=0.05,
        min_deviation_deadband=0.6,
    )
    assert pos is not None
    assert pos.z_score > 0
    assert pos.direction == "ABOVE"
    expected_pos_z = round((29.2 - pos.baseline_mean) / pos.baseline_std, 4)
    assert math.isclose(pos.z_score, expected_pos_z, abs_tol=0.01)

    # Negative deviation -> BELOW
    neg = compute_z_score_stats(
        observed_value=26.5,
        baseline_values=baseline,
        min_baseline_samples=8,
        min_meaningful_std=0.05,
        min_deviation_deadband=0.6,
    )
    assert neg is not None
    assert neg.z_score < 0
    assert neg.direction == "BELOW"
    expected_neg_z = round((26.5 - neg.baseline_mean) / neg.baseline_std, 4)
    assert math.isclose(neg.z_score, expected_neg_z, abs_tol=0.01)

    # Near-zero standard deviation -> suppressed safely (None)
    near_zero = compute_z_score_stats(
        observed_value=29.5,
        baseline_values=[28.000, 28.001, 28.000, 28.001, 28.000, 28.001, 28.000, 28.001],
        min_baseline_samples=8,
        min_meaningful_std=0.05,
        min_deviation_deadband=0.6,
    )
    assert near_zero is None


def test_detector_z_score_description_matches_stored_evidence_exactly() -> None:
    detector = StatisticalAnomalyDetector()
    base_ts = datetime(2026, 11, 26, 0, 0, 0, tzinfo=timezone.utc)
    baseline = [22.4, 22.7, 22.2, 22.6, 22.3, 22.8, 22.1, 22.5, 22.6, 22.4]
    for i, v in enumerate(baseline):
        detector.evaluate_batch([_sample("temperature", v, base_ts + timedelta(seconds=i))])

    findings = detector.evaluate_batch(
        [_sample("temperature", 26.5, base_ts + timedelta(seconds=10))]
    )
    stat = [f for f in findings if f.alert_type == "STATISTICAL_ANOMALY"]
    assert len(stat) == 1
    finding = stat[0]
    ev = finding.evidence
    recomputed = round((ev["observed_value"] - ev["baseline_mean"]) / ev["baseline_std"], 2)
    assert math.isclose(round(finding.z_score, 2), recomputed, abs_tol=0.02)
    assert ev["direction"] == "ABOVE"
    assert "ABOVE" in finding.description
    assert f"{abs(finding.z_score):.2f}" in finding.description


def test_temperature_spike_does_not_contaminate_nominal_baseline() -> None:
    detector = StatisticalAnomalyDetector()
    base_ts = datetime(2026, 11, 26, 0, 0, 0, tzinfo=timezone.utc)

    # 12 nominal readings around 22.5 °C
    for i in range(12):
        val = 22.5 + (0.2 if i % 2 == 0 else -0.2)
        detector.evaluate_batch([_sample("temperature", val, base_ts + timedelta(seconds=i))])

    # 25 temperature spike readings up to 77 °C (even with quality_status="NOMINAL" or "FAULT_SIMULATED")
    for j in range(25):
        spike_val = min(28.0 + j * 2.5, 77.0)
        detector.evaluate_batch(
            [
                _sample(
                    "temperature",
                    spike_val,
                    base_ts + timedelta(seconds=12 + j),
                    quality_status="FAULT_SIMULATED",
                )
            ]
        )

    # Baseline mean must remain near 22.5 °C, NOT contaminated to ~72 °C
    count, mean_val, _std_val = detector.get_baseline_summary()[("SAT-01", "temperature")]
    assert count == 12
    assert 22.0 <= mean_val <= 23.0

    # Returning smoothly to nominal 22.6 °C must NOT trigger false "BELOW baseline" z-score alert
    recovery_findings = detector.evaluate_batch(
        [_sample("temperature", 22.6, base_ts + timedelta(seconds=50), quality_status="NOMINAL")]
    )
    assert not any(f.alert_type == "STATISTICAL_ANOMALY" for f in recovery_findings)


def test_independent_baselines_per_satellite_and_sensor() -> None:
    detector = StatisticalAnomalyDetector()
    base_ts = datetime(2026, 11, 26, 0, 0, 0, tzinfo=timezone.utc)

    for i in range(10):
        detector.evaluate_batch(
            [
                _sample("temperature", 22.0 + (i % 2) * 0.3, base_ts + timedelta(seconds=i), satellite_id="SAT-01"),
                _sample("temperature", 31.0 + (i % 2) * 0.3, base_ts + timedelta(seconds=i), satellite_id="SAT-02"),
            ]
        )

    summary = detector.get_baseline_summary()
    assert 21.5 <= summary[("SAT-01", "temperature")][1] <= 22.8
    assert 30.5 <= summary[("SAT-02", "temperature")][1] <= 31.8

    # Explicit reset only clears requested satellite
    detector.reset_baseline(satellite_id="SAT-01")
    summary_after = detector.get_baseline_summary()
    assert ("SAT-01", "temperature") not in summary_after
    assert ("SAT-02", "temperature") in summary_after


def test_sensor_integrity_findings_are_warnings_not_critical() -> None:
    service = SensorIntegrityService(config=DetectionConfig(frozen_consecutive_samples=3))
    base_ts = datetime(2026, 11, 26, 0, 0, 0, tzinfo=timezone.utc)

    f1, _ = service.evaluate_batch([_sample("roll", None, base_ts)], simulator_running=True)
    f2, _ = service.evaluate_batch([_sample("pitch", 999.0, base_ts)], simulator_running=True)
    for i in range(3):
        f3, _ = service.evaluate_batch([_sample("yaw", 1.5, base_ts + timedelta(seconds=i))], simulator_running=True)

    assert f1[0].severity == "WARNING"
    assert f2[0].severity == "WARNING"
    assert f3[0].severity == "WARNING"


def test_cooldown_atomic_snapshot_and_recovery_auto_resolution(tmp_path: Path) -> None:
    db_file = tmp_path / "audit_pipeline.db"
    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    config = DetectionConfig(
        dedup_cooldown_seconds=10.0,
        recovery_consecutive_samples=3,
        auto_resolve_on_recovery=True,
    )
    pipeline = DetectionPipelineService(session_factory=TestingSessionLocal, config=config)

    base_ts = datetime(2026, 11, 26, 0, 0, 0, tzinfo=timezone.utc)

    # Warm up 10 nominal baseline readings
    for i in range(10):
        asyncio.run(
            pipeline.process_batch(
                [_sample("battery_voltage", 28.0 + (0.1 if i % 2 == 0 else -0.1), base_ts + timedelta(seconds=i))],
                simulator_running=True,
            )
        )

    # Inject CRITICAL engineering violation (< 21.5 V)
    created, updated, _ = asyncio.run(
        pipeline.process_batch(
            [_sample("battery_voltage", 20.5, base_ts + timedelta(seconds=20), quality_status="FAULT_SIMULATED")],
            simulator_running=True,
        )
    )
    assert any(a.alert_type == "ENGINEERING_LIMIT" and a.severity == "CRITICAL" for a in created)

    # Within 10s cooldown, lower-severity WARNING engineering reading (23.5 V) must NOT overwrite or inflate count
    _, updated_cool, _ = asyncio.run(
        pipeline.process_batch(
            [_sample("battery_voltage", 23.5, base_ts + timedelta(seconds=22), quality_status="FAULT_SIMULATED")],
            simulator_running=True,
        )
    )
    assert not any(a.alert_type == "ENGINEERING_LIMIT" for a in updated_cool)

    # After cooldown elapses (+12s), WARNING reading updates occurrence_count WITHOUT corrupting CRITICAL title/desc
    _, updated_after, _ = asyncio.run(
        pipeline.process_batch(
            [_sample("battery_voltage", 23.5, base_ts + timedelta(seconds=32), quality_status="FAULT_SIMULATED")],
            simulator_running=True,
        )
    )
    eng_updated = [a for a in updated_after if a.alert_type == "ENGINEERING_LIMIT"]
    assert len(eng_updated) == 1
    assert eng_updated[0].severity == "CRITICAL"
    assert "Critical engineering limit" in eng_updated[0].title
    assert "20.5" in eng_updated[0].description  # Atomic snapshot preserved!
    assert eng_updated[0].evidence["latest_observed_value"] == 23.5
    assert eng_updated[0].occurrence_count == 2

    # Recover with 3 consecutive nominal samples (rate <= 0.35 V/s) -> auto-resolves while preserving DB history!
    for idx, v in enumerate([27.9, 28.0, 28.1]):
        # Use 15s spacing on first recovery step so rate-of-change stays nominal
        ts = base_ts + timedelta(seconds=50 + idx * 15)
        asyncio.run(
            pipeline.process_batch(
                [_sample("battery_voltage", v, ts, quality_status="NOMINAL")],
                simulator_running=True,
            )
        )

    with TestingSessionLocal() as db:
        alerts, total, summary = AlertService.list_alerts(db=db, satellite_id="SAT-01")
        assert total >= 1
        assert summary.active == 0
        assert summary.resolved == total
        assert all(a.status == "RESOLVED" and a.resolved_at is not None for a in alerts)

    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
