"""NumPy-based synthetic satellite telemetry generator with fault injection."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np

from app.schemas.telemetry import (
    SENSOR_UNITS,
    ActiveFault,
    FaultType,
    SensorName,
    TelemetrySampleSchema,
)

SUPPORTED_SENSORS: tuple[SensorName, ...] = (
    "battery_voltage",
    "temperature",
    "roll",
    "pitch",
    "yaw",
)


@dataclass
class FaultState:
    """Tracks currently active fault scenarios inside the generator."""

    battery_drop: Optional[datetime] = None
    temperature_spike: Optional[datetime] = None
    attitude_disturbance: Optional[datetime] = None
    frozen_sensors: Dict[SensorName, datetime] = None  # type: ignore[assignment]
    missing_sensors: Dict[SensorName, datetime] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.frozen_sensors is None:
            self.frozen_sensors = {}
        if self.missing_sensors is None:
            self.missing_sensors = {}


class TelemetryGenerator:
    """Generates deterministic or stochastic synthetic telemetry for SAT-01."""

    def __init__(
        self,
        satellite_id: str = "SAT-01",
        nominal_voltage: float = 28.0,
        nominal_temperature: float = 22.5,
        seed: Optional[int] = None,
    ) -> None:
        self.satellite_id = satellite_id
        self.nominal_voltage = nominal_voltage
        self.nominal_temperature = nominal_temperature
        self.rng = np.random.default_rng(seed)

        self._step = 0
        self._battery_offset = 0.0
        self._temp_offset = 0.0
        self._faults = FaultState()
        self._frozen_values: Dict[SensorName, float] = {}
        self._last_values: Dict[SensorName, float] = {
            "battery_voltage": nominal_voltage,
            "temperature": nominal_temperature,
            "roll": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
        }

    def activate_fault(
        self,
        fault_type: FaultType,
        target_sensor: Optional[SensorName] = None,
        activated_at: Optional[datetime] = None,
    ) -> None:
        """Enable a synthetic fault scenario."""
        ts = activated_at or datetime.now(timezone.utc)
        if fault_type == "battery_drop":
            self._faults.battery_drop = ts
        elif fault_type == "temperature_spike":
            self._faults.temperature_spike = ts
        elif fault_type == "attitude_disturbance":
            self._faults.attitude_disturbance = ts
        elif fault_type == "frozen_sensor":
            sensor = target_sensor or "temperature"
            self._faults.frozen_sensors[sensor] = ts
            self._frozen_values[sensor] = self._last_values[sensor]
        elif fault_type == "missing_data":
            sensor = target_sensor or "temperature"
            self._faults.missing_sensors[sensor] = ts

    def clear_faults(self) -> None:
        """Clear active synthetic faults and allow offsets to recover smoothly."""
        self._faults = FaultState()
        self._frozen_values.clear()

    def get_active_faults(self) -> List[ActiveFault]:
        """Return a structured list of active fault scenarios."""
        items: List[ActiveFault] = []
        if self._faults.battery_drop is not None:
            items.append(
                ActiveFault(fault_type="battery_drop", activated_at=self._faults.battery_drop)
            )
        if self._faults.temperature_spike is not None:
            items.append(
                ActiveFault(
                    fault_type="temperature_spike",
                    activated_at=self._faults.temperature_spike,
                )
            )
        if self._faults.attitude_disturbance is not None:
            items.append(
                ActiveFault(
                    fault_type="attitude_disturbance",
                    activated_at=self._faults.attitude_disturbance,
                )
            )
        for sensor, ts in self._faults.frozen_sensors.items():
            items.append(
                ActiveFault(
                    fault_type="frozen_sensor",
                    target_sensor=sensor,
                    activated_at=ts,
                )
            )
        for sensor, ts in self._faults.missing_sensors.items():
            items.append(
                ActiveFault(
                    fault_type="missing_data",
                    target_sensor=sensor,
                    activated_at=ts,
                )
            )
        return items

    def generate_tick(self, timestamp: Optional[datetime] = None) -> List[TelemetrySampleSchema]:
        """Generate one synthetic reading per supported sensor using NumPy."""
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        self._step += 1
        phase = self._step * 0.12

        # 1. Battery voltage (V)
        battery_wave = 0.25 * float(np.sin(phase * 0.5))
        battery_noise = float(self.rng.normal(0.0, 0.06))
        if self._faults.battery_drop is not None:
            self._battery_offset = max(self._battery_offset - 0.45, -10.5)
        elif self._battery_offset < 0.0:
            # Smooth controlled recharge within nominal rate-of-change bounds
            self._battery_offset = min(self._battery_offset + 0.28, 0.0)
        battery_val = round(self.nominal_voltage + battery_wave + battery_noise + self._battery_offset, 3)
        battery_quality = (
            "FAULT_SIMULATED"
            if (self._faults.battery_drop is not None or self._battery_offset < -0.5)
            else "NOMINAL"
        )

        # 2. Temperature (°C)
        temp_wave = 1.1 * float(np.sin(phase * 0.35 + 0.6))
        temp_noise = float(self.rng.normal(0.0, 0.15))
        if self._faults.temperature_spike is not None:
            self._temp_offset = min(self._temp_offset + 3.2, 55.0)
        elif self._temp_offset > 0.0:
            # Smooth thermal cooldown within nominal rate-of-change bounds
            self._temp_offset = max(self._temp_offset - 1.4, 0.0)
        temp_val = round(self.nominal_temperature + temp_wave + temp_noise + self._temp_offset, 2)
        temp_quality = (
            "FAULT_SIMULATED"
            if (self._faults.temperature_spike is not None or self._temp_offset > 1.0)
            else "NOMINAL"
        )

        # 3-5. Attitude: roll, pitch, yaw (degrees)
        roll_base = 1.4 * float(np.sin(phase * 0.8)) + float(self.rng.normal(0.0, 0.18))
        pitch_base = 1.1 * float(np.cos(phase * 0.65)) + float(self.rng.normal(0.0, 0.15))
        yaw_base = 2.8 * float(np.sin(phase * 0.4 + 1.1)) + float(self.rng.normal(0.0, 0.25))

        if self._faults.attitude_disturbance is not None:
            roll_base += float(self.rng.choice([-1.0, 1.0]) * self.rng.uniform(16.0, 28.0))
            pitch_base += float(self.rng.choice([-1.0, 1.0]) * self.rng.uniform(14.0, 24.0))
            yaw_base += float(self.rng.choice([-1.0, 1.0]) * self.rng.uniform(20.0, 35.0))
            attitude_quality = "FAULT_SIMULATED"
        else:
            attitude_quality = "NOMINAL"

        raw_values: Dict[SensorName, tuple[float, str]] = {
            "battery_voltage": (battery_val, battery_quality),
            "temperature": (temp_val, temp_quality),
            "roll": (round(roll_base, 3), attitude_quality),
            "pitch": (round(pitch_base, 3), attitude_quality),
            "yaw": (round(yaw_base, 3), attitude_quality),
        }

        samples: List[TelemetrySampleSchema] = []
        for sensor in SUPPORTED_SENSORS:
            val, quality = raw_values[sensor]

            if sensor in self._faults.missing_sensors:
                samples.append(
                    TelemetrySampleSchema(
                        satellite_id=self.satellite_id,
                        sensor_name=sensor,
                        sensor_value=None,
                        unit=SENSOR_UNITS[sensor],
                        timestamp=ts,
                        quality_status="MISSING",
                    )
                )
                continue

            if sensor in self._faults.frozen_sensors:
                frozen_val = self._frozen_values.get(sensor, self._last_values[sensor])
                self._frozen_values[sensor] = frozen_val
                samples.append(
                    TelemetrySampleSchema(
                        satellite_id=self.satellite_id,
                        sensor_name=sensor,
                        sensor_value=frozen_val,
                        unit=SENSOR_UNITS[sensor],
                        timestamp=ts,
                        quality_status="FROZEN",
                    )
                )
                continue

            self._last_values[sensor] = val
            samples.append(
                TelemetrySampleSchema(
                    satellite_id=self.satellite_id,
                    sensor_name=sensor,
                    sensor_value=val,
                    unit=SENSOR_UNITS[sensor],
                    timestamp=ts,
                    quality_status=quality,
                )
            )

        return samples
