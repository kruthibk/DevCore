"""Centralized configuration for statistical anomaly detection and sensor integrity."""

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class SensorLimits:
    """Operational engineering bounds and physically valid sensor bounds."""

    unit: str
    engineering_warning: Tuple[float, float]
    engineering_critical: Tuple[float, float]
    physical_valid_range: Tuple[float, float]
    max_rate_per_sec: float
    min_meaningful_std: float
    min_deviation_deadband: float


DEFAULT_SENSOR_LIMITS: Dict[str, SensorLimits] = {
    "battery_voltage": SensorLimits(
        unit="V",
        engineering_warning=(24.0, 29.6),
        engineering_critical=(21.5, 30.8),
        physical_valid_range=(0.0, 60.0),
        max_rate_per_sec=0.35,
        min_meaningful_std=0.05,
        min_deviation_deadband=0.6,
    ),
    "temperature": SensorLimits(
        unit="°C",
        engineering_warning=(5.0, 40.0),
        engineering_critical=(-5.0, 55.0),
        physical_valid_range=(-150.0, 200.0),
        max_rate_per_sec=1.8,
        min_meaningful_std=0.1,
        min_deviation_deadband=2.2,
    ),
    "roll": SensorLimits(
        unit="degrees",
        engineering_warning=(-10.0, 10.0),
        engineering_critical=(-22.0, 22.0),
        physical_valid_range=(-180.0, 180.0),
        max_rate_per_sec=8.0,
        min_meaningful_std=0.1,
        min_deviation_deadband=2.5,
    ),
    "pitch": SensorLimits(
        unit="degrees",
        engineering_warning=(-10.0, 10.0),
        engineering_critical=(-22.0, 22.0),
        physical_valid_range=(-180.0, 180.0),
        max_rate_per_sec=8.0,
        min_meaningful_std=0.1,
        min_deviation_deadband=2.5,
    ),
    "yaw": SensorLimits(
        unit="degrees",
        engineering_warning=(-14.0, 14.0),
        engineering_critical=(-28.0, 28.0),
        physical_valid_range=(-180.0, 180.0),
        max_rate_per_sec=10.0,
        min_meaningful_std=0.1,
        min_deviation_deadband=4.0,
    ),
}


@dataclass(frozen=True)
class DetectionConfig:
    """Configurable thresholds for statistical anomaly and sensor integrity checks."""

    rolling_window_size: int = 30
    min_baseline_samples: int = 8
    z_score_warning: float = 3.5
    z_score_critical: float = 5.0
    frozen_consecutive_samples: int = 6
    frozen_tolerance: float = 1e-9
    stale_timeout_seconds: float = 6.0
    dedup_cooldown_seconds: float = 10.0
    recovery_consecutive_samples: int = 5
    auto_resolve_on_recovery: bool = True
    exclude_fault_labeled_from_baseline: bool = True
    sensor_limits: Dict[str, SensorLimits] = field(
        default_factory=lambda: dict(DEFAULT_SENSOR_LIMITS)
    )
