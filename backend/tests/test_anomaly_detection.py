"""Deterministic tests for StatisticalAnomalyDetector (NumPy/Pandas/SciPy)."""

from datetime import datetime, timedelta, timezone

from app.core.detection_config import DetectionConfig
from app.schemas.telemetry import SENSOR_UNITS, TelemetrySampleSchema
from app.services.anomaly_detector import StatisticalAnomalyDetector
from app.services.telemetry_generator import TelemetryGenerator


def _make_sample(
    sensor: str,
    value: float,
    ts: datetime,
    quality_status: str = "NOMINAL",
) -> TelemetrySampleSchema:
    return TelemetrySampleSchema(
        satellite_id="SAT-01",
        sensor_name=sensor,  # type: ignore[arg-type]
        sensor_value=value,
        unit=SENSOR_UNITS[sensor],
        timestamp=ts,
        quality_status=quality_status,  # type: ignore[arg-type]
    )


def test_normal_telemetry_fluctuations_produce_zero_alerts() -> None:
    detector = StatisticalAnomalyDetector()
    generator = TelemetryGenerator(seed=42)
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    all_findings = []
    for step in range(30):
        samples = generator.generate_tick(timestamp=base_ts + timedelta(seconds=step))
        all_findings.extend(detector.evaluate_batch(samples))

    assert all_findings == []


def test_insufficient_baseline_data_does_not_trigger_statistical_alert() -> None:
    config = DetectionConfig(min_baseline_samples=8)
    detector = StatisticalAnomalyDetector(config=config)
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    # Feed only 5 nominal baseline samples (< 8), then a moderate deviation still inside engineering limits
    findings = []
    for idx, val in enumerate([28.0, 28.1, 27.9, 28.05, 27.95, 29.3]):
        findings.extend(
            detector.evaluate_batch(
                [_make_sample("battery_voltage", val, base_ts + timedelta(seconds=idx * 5))]
            )
        )

    assert not any(f.alert_type == "STATISTICAL_ANOMALY" for f in findings)


def test_zero_standard_deviation_does_not_crash_or_divide_by_zero() -> None:
    config = DetectionConfig(min_baseline_samples=5)
    detector = StatisticalAnomalyDetector(config=config)
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    # Feed 8 identical values (std == 0) then a small step within limits
    findings = []
    for idx in range(8):
        findings.extend(
            detector.evaluate_batch(
                [_make_sample("temperature", 22.0, base_ts + timedelta(seconds=idx))]
            )
        )
    findings.extend(
        detector.evaluate_batch(
            [_make_sample("temperature", 22.04, base_ts + timedelta(seconds=9))]
        )
    )

    assert not any(f.alert_type == "STATISTICAL_ANOMALY" for f in findings)


def test_strong_battery_voltage_drop_detected_independently_of_quality_label() -> None:
    detector = StatisticalAnomalyDetector()
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    # Build 12-sample realistic baseline (even labeling samples NOMINAL on the fault!)
    baseline = [28.0, 28.08, 27.94, 28.04, 27.96, 28.1, 27.92, 28.05, 28.01, 27.97, 28.06, 27.98]
    for idx, v in enumerate(baseline):
        detector.evaluate_batch([_make_sample("battery_voltage", v, base_ts + timedelta(seconds=idx))])

    # Sudden/strong drop even with quality_status="NOMINAL" -> detector must ignore label and detect numerically
    findings = detector.evaluate_batch(
        [_make_sample("battery_voltage", 21.0, base_ts + timedelta(seconds=12), quality_status="NOMINAL")]
    )
    types = {f.alert_type for f in findings}
    assert "STATISTICAL_ANOMALY" in types
    assert "RATE_OF_CHANGE" in types
    assert "ENGINEERING_LIMIT" in types
    assert any(f.severity == "CRITICAL" for f in findings)


def test_temperature_spike_and_attitude_deviation_detected() -> None:
    detector = StatisticalAnomalyDetector()
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    for idx in range(12):
        offset = 0.2 if idx % 2 == 0 else -0.2
        detector.evaluate_batch(
            [
                _make_sample("temperature", 22.5 + offset, base_ts + timedelta(seconds=idx)),
                _make_sample("roll", 0.5 + offset, base_ts + timedelta(seconds=idx)),
            ]
        )

    spike_findings = detector.evaluate_batch(
        [
            _make_sample("temperature", 45.0, base_ts + timedelta(seconds=12)),
            _make_sample("roll", 18.0, base_ts + timedelta(seconds=12)),
        ]
    )

    temp_types = {f.alert_type for f in spike_findings if f.sensor_name == "temperature"}
    roll_types = {f.alert_type for f in spike_findings if f.sensor_name == "roll"}
    assert "STATISTICAL_ANOMALY" in temp_types
    assert "RATE_OF_CHANGE" in temp_types
    assert "ENGINEERING_LIMIT" in temp_types
    assert "STATISTICAL_ANOMALY" in roll_types
    assert "RATE_OF_CHANGE" in roll_types
    assert "ENGINEERING_LIMIT" in roll_types


def test_rate_of_change_and_engineering_limits_distinguished() -> None:
    detector = StatisticalAnomalyDetector()
    base_ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)

    # Gradual step outside engineering warning limit (temperature 41.0 -> 41.5 in 1s: rate=0.5 < 1.8 limit)
    detector.evaluate_batch([_make_sample("temperature", 40.5, base_ts)])
    eng_only = detector.evaluate_batch([_make_sample("temperature", 41.2, base_ts + timedelta(seconds=1))])
    assert [f.alert_type for f in eng_only] == ["ENGINEERING_LIMIT"]
    assert eng_only[0].severity == "WARNING"

    # Rapid jump inside engineering bounds (temperature 20.0 -> 25.0 in 1s: rate=5.0 > 1.8 limit)
    detector2 = StatisticalAnomalyDetector()
    detector2.evaluate_batch([_make_sample("temperature", 20.0, base_ts)])
    roc_only = detector2.evaluate_batch([_make_sample("temperature", 25.0, base_ts + timedelta(seconds=1))])
    assert [f.alert_type for f in roc_only] == ["RATE_OF_CHANGE"]
