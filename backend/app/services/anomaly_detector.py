"""Numerical statistical anomaly detector using NumPy, Pandas, and SciPy."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Deque, Dict, List, Literal, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from app.core.detection_config import DetectionConfig
from app.schemas.alerts import AlertSeverity, AlertType
from app.schemas.telemetry import TelemetrySampleSchema

SensorKey = Tuple[str, str]  # (satellite_id, sensor_name)
ANGULAR_SENSORS = ("roll", "pitch", "yaw")


def circular_angle_delta_deg(target_deg: float, reference_deg: float) -> float:
    """Return shortest signed angular difference in degrees within [-180, 180)."""
    return ((float(target_deg) - float(reference_deg) + 180.0) % 360.0) - 180.0


def _circular_mean_std_deg(values_deg: Sequence[float]) -> Tuple[float, float]:
    """Compute circular mean (degrees) and angular sample std (degrees) for wrapped angles."""
    radians = np.deg2rad(np.asarray(list(values_deg), dtype="float64"))
    sin_mean = float(np.mean(np.sin(radians)))
    cos_mean = float(np.mean(np.cos(radians)))
    mean_deg = float(np.rad2deg(math.atan2(sin_mean, cos_mean)))
    if len(values_deg) < 2:
        return mean_deg, 0.0
    diffs = np.asarray([circular_angle_delta_deg(v, mean_deg) for v in values_deg], dtype="float64")
    std_deg = float(math.sqrt(float(np.sum(diffs ** 2)) / (len(values_deg) - 1)))
    return mean_deg, std_deg


@dataclass(frozen=True)
class ZScoreStats:
    """Authoritative z-score calculation shared across detector, evidence, and UI text."""

    observed_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    direction: Literal["ABOVE", "BELOW"]
    window_samples: int
    two_tailed_p: float


def compute_z_score_stats(
    observed_value: float,
    baseline_values: Sequence[float],
    min_baseline_samples: int,
    min_meaningful_std: float,
    min_deviation_deadband: float,
    angular: bool = False,
) -> Optional[ZScoreStats]:
    """Compute baseline mean, std, and z-score atomically from one authoritative source.

    When angular=True, computes circular mean/std and shortest signed angle delta [-180, 180).
    Returns None when baseline size is insufficient, std is zero/near-zero, or
    observed deviation is below the sensor noise deadband.
    """
    if len(baseline_values) < min_baseline_samples:
        return None
    if not math.isfinite(observed_value):
        return None

    if angular:
        baseline_mean, baseline_std = _circular_mean_std_deg(baseline_values)
        deviation = circular_angle_delta_deg(observed_value, baseline_mean)
    else:
        series = pd.Series(list(baseline_values), dtype="float64")
        baseline_mean = float(series.mean())
        baseline_std = float(series.std(ddof=1))
        deviation = observed_value - baseline_mean

    if not math.isfinite(baseline_std) or baseline_std < min_meaningful_std:
        return None

    if abs(deviation) < min_deviation_deadband:
        return None

    z_score = deviation / baseline_std
    direction: Literal["ABOVE", "BELOW"] = "ABOVE" if z_score >= 0.0 else "BELOW"
    two_tailed_p = float(2.0 * stats.norm.sf(abs(z_score)))

    return ZScoreStats(
        observed_value=round(observed_value, 4),
        baseline_mean=round(baseline_mean, 4),
        baseline_std=round(baseline_std, 4),
        z_score=round(z_score, 4),
        direction=direction,
        window_samples=len(baseline_values),
        two_tailed_p=round(two_tailed_p, 8),
    )


@dataclass
class AnomalyFinding:
    """Structured numerical anomaly candidate emitted by StatisticalAnomalyDetector."""

    satellite_id: str
    sensor_name: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    observed_value: float
    expected_range: str
    z_score: Optional[float]
    reason_code: str
    evidence: Dict[str, Any]
    detected_at: datetime


class StatisticalAnomalyDetector:
    """Analyses raw numerical telemetry using rolling baseline, z-score, rate-of-change, and limits."""

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        self.config = config or DetectionConfig()
        self._windows: Dict[SensorKey, Deque[Tuple[datetime, float]]] = {}
        self._last_samples: Dict[SensorKey, Tuple[datetime, float]] = {}
        self._clean_streaks: Dict[SensorKey, int] = {}

    def reset_baseline(
        self,
        satellite_id: Optional[str] = None,
        sensor_name: Optional[str] = None,
    ) -> None:
        """Explicitly clear rolling baselines for testing or operator recalibration."""
        if satellite_id is None and sensor_name is None:
            self._windows.clear()
            self._last_samples.clear()
            self._clean_streaks.clear()
            return
        keys_to_remove = [
            key
            for key in self._windows
            if (satellite_id is None or key[0] == satellite_id)
            and (sensor_name is None or key[1] == sensor_name)
        ]
        for key in keys_to_remove:
            self._windows.pop(key, None)
            self._last_samples.pop(key, None)
            self._clean_streaks.pop(key, None)

    def get_baseline_summary(self) -> Dict[SensorKey, Tuple[int, Optional[float], Optional[float]]]:
        """Return (sample_count, rolling_mean, rolling_std) keyed by (satellite_id, sensor_name)."""
        summary: Dict[SensorKey, Tuple[int, Optional[float], Optional[float]]] = {}
        for key, window in self._windows.items():
            if not window:
                summary[key] = (0, None, None)
                continue
            vals = [val for _, val in window]
            if key[1] in ANGULAR_SENSORS:
                mean_raw, std_raw = _circular_mean_std_deg(vals)
                mean_val = round(mean_raw, 4)
                std_val = round(std_raw, 4)
            else:
                series = pd.Series(vals, dtype="float64")
                mean_val = round(float(series.mean()), 4)
                std_val = round(float(series.std(ddof=1)), 4) if len(series) >= 2 else 0.0
            summary[key] = (len(window), mean_val, std_val)
        return summary

    def get_recovered_channels(self, satellite_id: str, required_clean: int) -> List[str]:
        """Return sensors that have achieved >= required_clean consecutive nominal samples."""
        return [
            sensor
            for (sat_id, sensor), streak in self._clean_streaks.items()
            if sat_id == satellite_id and streak >= required_clean
        ]

    def evaluate_batch(self, samples: List[TelemetrySampleSchema]) -> List[AnomalyFinding]:
        """Evaluate finite telemetry samples using independent statistical and physical checks.

        Detection decisions never depend on sample.quality_status.
        Simulated fault samples and numerically anomalous samples are excluded from
        updating the nominal rolling baseline so fault bursts do not distort recovery.
        """
        findings: List[AnomalyFinding] = []
        ordered_samples = sorted(
            samples,
            key=lambda s: (s.satellite_id, s.sensor_name, s.timestamp),
        )

        for sample in ordered_samples:
            if sample.sensor_value is None:
                continue
            val = float(sample.sensor_value)
            if not math.isfinite(val):
                continue

            sensor = sample.sensor_name
            key: SensorKey = (sample.satellite_id, sensor)
            limits = self.config.sensor_limits.get(sensor)
            if limits is None:
                continue

            window = self._windows.setdefault(
                key,
                deque(maxlen=self.config.rolling_window_size),
            )
            last_sample = self._last_samples.get(key)

            # Enforce monotonic timestamp ordering per (satellite, sensor)
            if last_sample is not None and sample.timestamp <= last_sample[0]:
                continue

            sample_findings: List[AnomalyFinding] = []

            # A. Engineering Limit Detection (distinct from statistical deviations)
            crit_min, crit_max = limits.engineering_critical
            warn_min, warn_max = limits.engineering_warning
            if val < crit_min or val > crit_max:
                sample_findings.append(
                    AnomalyFinding(
                        satellite_id=sample.satellite_id,
                        sensor_name=sensor,
                        alert_type="ENGINEERING_LIMIT",
                        severity="CRITICAL",
                        title=f"Critical engineering limit exceeded on {sensor}",
                        description=(
                            f"{self._human_name(sensor)} reading ({val} {limits.unit}) exceeded critical "
                            f"engineering bounds [{crit_min}, {crit_max}] {limits.unit}."
                        ),
                        observed_value=val,
                        expected_range=f"[{crit_min}, {crit_max}] {limits.unit}",
                        z_score=None,
                        reason_code="ENGINEERING_CRITICAL_LIMIT",
                        evidence={
                            "observed_value": val,
                            "critical_bounds": [crit_min, crit_max],
                            "warning_bounds": [warn_min, warn_max],
                            "unit": limits.unit,
                        },
                        detected_at=sample.timestamp,
                    )
                )
            elif val < warn_min or val > warn_max:
                sample_findings.append(
                    AnomalyFinding(
                        satellite_id=sample.satellite_id,
                        sensor_name=sensor,
                        alert_type="ENGINEERING_LIMIT",
                        severity="WARNING",
                        title=f"Engineering warning limit exceeded on {sensor}",
                        description=(
                            f"{self._human_name(sensor)} reading ({val} {limits.unit}) is outside nominal "
                            f"engineering bounds [{warn_min}, {warn_max}] {limits.unit}."
                        ),
                        observed_value=val,
                        expected_range=f"[{warn_min}, {warn_max}] {limits.unit}",
                        z_score=None,
                        reason_code="ENGINEERING_WARNING_LIMIT",
                        evidence={
                            "observed_value": val,
                            "warning_bounds": [warn_min, warn_max],
                            "critical_bounds": [crit_min, crit_max],
                            "unit": limits.unit,
                        },
                        detected_at=sample.timestamp,
                    )
                )

            is_angular = sensor in ANGULAR_SENSORS

            # B. Rate-of-Change Detection (uses circular delta for attitude angles)
            if last_sample is not None:
                prev_ts, prev_val = last_sample
                dt_seconds = (sample.timestamp - prev_ts).total_seconds()
                if dt_seconds > 0:
                    delta = (
                        circular_angle_delta_deg(val, prev_val)
                        if is_angular
                        else (val - prev_val)
                    )
                    rate_per_sec = abs(delta) / dt_seconds
                    if rate_per_sec > limits.max_rate_per_sec:
                        roc_severity: AlertSeverity = (
                            "CRITICAL" if rate_per_sec >= 2.0 * limits.max_rate_per_sec else "WARNING"
                        )
                        direction_verb = "increased" if delta > 0 else "decreased"
                        sample_findings.append(
                            AnomalyFinding(
                                satellite_id=sample.satellite_id,
                                sensor_name=sensor,
                                alert_type="RATE_OF_CHANGE",
                                severity=roc_severity,
                                title=f"Rapid {sensor} rate-of-change detected",
                                description=(
                                    f"{self._human_name(sensor)} {direction_verb} faster than the configured "
                                    f"rate-of-change limit ({rate_per_sec:.3f} {limits.unit}/s vs limit "
                                    f"{limits.max_rate_per_sec} {limits.unit}/s)."
                                ),
                                observed_value=val,
                                expected_range=f"<= {limits.max_rate_per_sec} {limits.unit}/s",
                                z_score=None,
                                reason_code="RATE_OF_CHANGE_EXCEEDED",
                                evidence={
                                    "previous_value": prev_val,
                                    "observed_value": val,
                                    "delta": round(delta, 4),
                                    "angular_wrapped": is_angular,
                                    "dt_seconds": round(dt_seconds, 4),
                                    "rate_per_sec": round(rate_per_sec, 4),
                                    "max_rate_per_sec": limits.max_rate_per_sec,
                                    "unit": limits.unit,
                                },
                                detected_at=sample.timestamp,
                            )
                        )

            # C. Rolling Baseline + Z-score Detection (single authoritative calculation)
            z_stats = compute_z_score_stats(
                observed_value=val,
                baseline_values=[v for _, v in window],
                min_baseline_samples=self.config.min_baseline_samples,
                min_meaningful_std=limits.min_meaningful_std,
                min_deviation_deadband=limits.min_deviation_deadband,
                angular=is_angular,
            )
            if z_stats is not None and abs(z_stats.z_score) >= self.config.z_score_warning:
                z_severity: AlertSeverity = (
                    "CRITICAL"
                    if abs(z_stats.z_score) >= self.config.z_score_critical
                    else "WARNING"
                )
                sample_findings.append(
                    AnomalyFinding(
                        satellite_id=sample.satellite_id,
                        sensor_name=sensor,
                        alert_type="STATISTICAL_ANOMALY",
                        severity=z_severity,
                        title=f"Statistical deviation detected on {sensor}",
                        description=(
                            f"{self._human_name(sensor)} ({z_stats.observed_value} {limits.unit}) is "
                            f"{abs(z_stats.z_score):.2f} standard deviations {z_stats.direction} "
                            f"its rolling baseline ({z_stats.baseline_mean:.3f} ± "
                            f"{z_stats.baseline_std:.3f} {limits.unit})."
                        ),
                        observed_value=z_stats.observed_value,
                        expected_range=(
                            f"{z_stats.baseline_mean:.3f} ± "
                            f"{self.config.z_score_warning * z_stats.baseline_std:.3f} {limits.unit}"
                        ),
                        z_score=z_stats.z_score,
                        reason_code="Z_SCORE_DEVIATION",
                        evidence={
                            "observed_value": z_stats.observed_value,
                            "baseline_mean": z_stats.baseline_mean,
                            "baseline_std": z_stats.baseline_std,
                            "rolling_mean": z_stats.baseline_mean,
                            "rolling_std": z_stats.baseline_std,
                            "window_samples": z_stats.window_samples,
                            "z_score": z_stats.z_score,
                            "direction": z_stats.direction,
                            "angular_wrapped": is_angular,
                            "z_threshold_warning": self.config.z_score_warning,
                            "z_threshold_critical": self.config.z_score_critical,
                            "illustrative_two_tailed_p": z_stats.two_tailed_p,
                            "unit": limits.unit,
                        },
                        detected_at=sample.timestamp,
                    )
                )

            findings.extend(sample_findings)
            self._last_samples[key] = (sample.timestamp, val)

            # Update clean recovery streak
            if sample_findings:
                self._clean_streaks[key] = 0
            else:
                self._clean_streaks[key] = self._clean_streaks.get(key, 0) + 1

            # Baseline contamination safeguard:
            # Exclude explicitly simulated fault samples AND numerically anomalous samples
            # once the baseline has warmed up so fault bursts never distort nominal baselines.
            is_fault_labeled = (
                self.config.exclude_fault_labeled_from_baseline
                and sample.quality_status != "NOMINAL"
            )
            is_numerical_anomaly = len(sample_findings) > 0
            if not is_fault_labeled and not is_numerical_anomaly:
                window.append((sample.timestamp, val))

        return findings

    @staticmethod
    def _human_name(sensor_name: str) -> str:
        return sensor_name.replace("_", " ").capitalize()
