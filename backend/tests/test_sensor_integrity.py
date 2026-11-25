"""Deterministic tests for SensorIntegrityService (MISSING, FROZEN, INVALID, STALE)."""

from datetime import datetime, timedelta, timezone

from app.core.detection_config import DetectionConfig
from app.schemas.telemetry import SENSOR_UNITS, TelemetrySampleSchema
from app.services.sensor_integrity_service import SensorIntegrityService


def _sample(sensor: str, value, ts: datetime) -> TelemetrySampleSchema:
    return TelemetrySampleSchema(
        satellite_id="SAT-01",
        sensor_name=sensor,  # type: ignore[arg-type]
        sensor_value=value,
        unit=SENSOR_UNITS[sensor],
        timestamp=ts,
        quality_status="NOMINAL",
    )


def test_missing_reading_detected_and_excluded_from_valid_samples() -> None:
    service = SensorIntegrityService()
    ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    findings, valid = service.evaluate_batch(
        [_sample("pitch", None, ts), _sample("temperature", 22.4, ts)],
        simulator_running=True,
    )

    assert len(findings) == 1
    assert findings[0].sensor_name == "pitch"
    assert findings[0].integrity_status == "MISSING"
    assert findings[0].observed_value is None
    assert [s.sensor_name for s in valid] == ["temperature"]


def test_frozen_sensor_requires_configured_consecutive_identical_samples() -> None:
    config = DetectionConfig(frozen_consecutive_samples=6)
    service = SensorIntegrityService(config=config)
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    # First 5 identical values should NOT falsely flag FROZEN
    for idx in range(5):
        findings, _ = service.evaluate_batch(
            [_sample("battery_voltage", 28.0, base_ts + timedelta(seconds=idx))],
            simulator_running=True,
        )
        assert findings == []

    # 6th consecutive identical value triggers FROZEN
    findings_6, _ = service.evaluate_batch(
        [_sample("battery_voltage", 28.0, base_ts + timedelta(seconds=5))],
        simulator_running=True,
    )
    assert len(findings_6) == 1
    assert findings_6[0].integrity_status == "FROZEN"
    assert findings_6[0].evidence["consecutive_samples"] == 6


def test_invalid_values_and_non_finite_readings_detected() -> None:
    service = SensorIntegrityService()
    ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    # Out of physical range (-180..180 for roll; -150..200 for temperature) and NaN
    findings, valid = service.evaluate_batch(
        [
            _sample("roll", 245.0, ts),
            _sample("temperature", float("nan"), ts),
            _sample("battery_voltage", 28.0, ts),
        ],
        simulator_running=True,
    )

    assert len(findings) == 2
    assert all(f.integrity_status == "INVALID" for f in findings)
    assert {f.sensor_name for f in findings} == {"roll", "temperature"}
    assert [s.sensor_name for s in valid] == ["battery_voltage"]


def test_stale_sensor_detected_only_when_simulator_running() -> None:
    config = DetectionConfig(stale_timeout_seconds=5.0)
    service = SensorIntegrityService(config=config)
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    service.evaluate_batch(
        [_sample("yaw", 1.2, base_ts), _sample("temperature", 22.1, base_ts)],
        simulator_running=True,
    )

    # Only temperature updates at +7s; yaw is stale
    service.evaluate_batch(
        [_sample("temperature", 22.3, base_ts + timedelta(seconds=7))],
        simulator_running=True,
    )
    stale_findings = service.evaluate_staleness(
        now=base_ts + timedelta(seconds=7),
        simulator_running=True,
    )
    assert [f.sensor_name for f in stale_findings] == ["yaw"]
    assert stale_findings[0].integrity_status == "STALE"

    # When simulator is stopped, must NOT falsely mark sensors stale
    stopped_findings = service.evaluate_staleness(
        now=base_ts + timedelta(seconds=300),
        simulator_running=False,
    )
    assert stopped_findings == []
    snapshots = {s.sensor_name: s for s in service.get_channel_snapshots(simulator_running=False)}
    assert snapshots["temperature"].integrity_status == "STREAM_INACTIVE"
    assert snapshots["yaw"].integrity_status == "STREAM_INACTIVE"
