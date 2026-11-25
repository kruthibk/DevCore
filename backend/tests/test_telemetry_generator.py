"""Deterministic unit tests for NumPy-based TelemetryGenerator and fault injection."""

from datetime import datetime, timezone

from app.services.telemetry_generator import TelemetryGenerator


def test_normal_telemetry_generation_sensors_and_timestamps() -> None:
    gen = TelemetryGenerator(satellite_id="SAT-01", seed=42)
    samples = gen.generate_tick()

    assert len(samples) == 5
    by_sensor = {s.sensor_name: s for s in samples}
    assert set(by_sensor.keys()) == {
        "battery_voltage",
        "temperature",
        "roll",
        "pitch",
        "yaw",
    }

    for sample in samples:
        assert sample.satellite_id == "SAT-01"
        assert sample.quality_status == "NOMINAL"
        assert sample.timestamp.tzinfo is not None
        assert sample.timestamp.tzinfo == timezone.utc
        assert sample.sensor_value is not None

    # Battery nominal ~28V, temperature ~22.5C, attitude in bounded operating range
    assert 26.5 <= by_sensor["battery_voltage"].sensor_value <= 29.5
    assert by_sensor["battery_voltage"].unit == "V"
    assert 19.0 <= by_sensor["temperature"].sensor_value <= 26.0
    assert by_sensor["temperature"].unit == "°C"
    assert -6.0 <= by_sensor["roll"].sensor_value <= 6.0
    assert -6.0 <= by_sensor["pitch"].sensor_value <= 6.0
    assert -8.0 <= by_sensor["yaw"].sensor_value <= 8.0


def test_deterministic_seed_produces_reproducible_readings() -> None:
    ts = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)
    gen_a = TelemetryGenerator(seed=12345)
    gen_b = TelemetryGenerator(seed=12345)

    assert gen_a.generate_tick(ts) == gen_b.generate_tick(ts)
    assert gen_a.generate_tick(ts) == gen_b.generate_tick(ts)


def test_battery_drop_fault_gradually_decreases_voltage() -> None:
    gen = TelemetryGenerator(seed=7)
    baseline = {s.sensor_name: s for s in gen.generate_tick()}["battery_voltage"].sensor_value

    gen.activate_fault("battery_drop")
    voltages = []
    qualities = []
    for _ in range(5):
        by_sensor = {s.sensor_name: s for s in gen.generate_tick()}
        voltages.append(by_sensor["battery_voltage"].sensor_value)
        qualities.append(by_sensor["battery_voltage"].quality_status)

    assert all(q == "FAULT_SIMULATED" for q in qualities)
    assert voltages[-1] < baseline - 1.5
    assert voltages[-1] < voltages[0]


def test_temperature_spike_fault_raises_temperature() -> None:
    gen = TelemetryGenerator(seed=9)
    baseline = {s.sensor_name: s for s in gen.generate_tick()}["temperature"].sensor_value

    gen.activate_fault("temperature_spike")
    temps = []
    for _ in range(6):
        by_sensor = {s.sensor_name: s for s in gen.generate_tick()}
        temps.append(by_sensor["temperature"].sensor_value)
        assert by_sensor["temperature"].quality_status == "FAULT_SIMULATED"

    assert temps[-1] > baseline + 15.0


def test_attitude_disturbance_fault_amplifies_angles() -> None:
    gen = TelemetryGenerator(seed=11)
    gen.activate_fault("attitude_disturbance")
    by_sensor = {s.sensor_name: s for s in gen.generate_tick()}

    assert by_sensor["roll"].quality_status == "FAULT_SIMULATED"
    assert abs(by_sensor["roll"].sensor_value) > 10.0
    assert abs(by_sensor["yaw"].sensor_value) > 10.0


def test_frozen_sensor_keeps_constant_value() -> None:
    gen = TelemetryGenerator(seed=21)
    first = {s.sensor_name: s for s in gen.generate_tick()}
    frozen_target = first["temperature"].sensor_value

    gen.activate_fault("frozen_sensor", target_sensor="temperature")
    for _ in range(4):
        tick = {s.sensor_name: s for s in gen.generate_tick()}
        assert tick["temperature"].sensor_value == frozen_target
        assert tick["temperature"].quality_status == "FROZEN"


def test_missing_sensor_emits_null_value_and_missing_quality() -> None:
    gen = TelemetryGenerator(seed=33)
    gen.activate_fault("missing_data", target_sensor="battery_voltage")
    tick = {s.sensor_name: s for s in gen.generate_tick()}

    assert tick["battery_voltage"].sensor_value is None
    assert tick["battery_voltage"].quality_status == "MISSING"
    assert tick["temperature"].sensor_value is not None
