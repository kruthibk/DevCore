"""Numerical statistical anomaly detector using NumPy, Pandas, and SciPy."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import math
from typing import Any, Deque, Dict, List, Optional, Tuple

import pandas as pd
from scipy import stats

from app.core.detection_config import DetectionConfig
from app.schemas.alerts import AlertSeverity, AlertType
from app.schemas.telemetry import TelemetrySampleSchema


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
        self._windows: Dict[str, Deque[Tuple[datetime, float]]] = {}

    def get_baseline_summary(self) -> Dict[str, Tuple[int, Optional[float], Optional[float]]]:
        """Return (sample_count, rolling_mean, rolling_std) for each tracked sensor."""
        summary: Dict[str, Tuple[int, Optional[float], Optional[float]]] = {}
        for sensor, window in self._windows.items():
            if not window:
                summary[sensor] = (0, None, None)
                continue
            series = pd.Series([val for _, val in window], dtype="float64")
            mean_val = round(float(series.mean()), 4)
            std_val = round(float(series.std(ddof=1)), 4) if len(series) >= 2 else 0.0
            summary[sensor] = (len(window), mean_val, std_val)
        return summary

    def evaluate_batch(self, samples: List[TelemetrySampleSchema]) -> List[AnomalyFinding]:
        """Evaluate finite telemetry samples using independent statistical and physical checks.

        Does NOT inspect sample.quality_status.
        """
        findings: List[AnomalyFinding] = []

        for sample in samples:
            if sample.sensor_value is None:
                continue
            val = float(sample.sensor_value)
            if not math.isfinite(val):
                continue

            sensor = sample.sensor_name
            limits = self.config.sensor_limits.get(sensor)
            if limits is None:
                continue

            window = self._windows.setdefault(
                sensor,
                deque(maxlen=self.config.rolling_window_size),
            )

            # A. Engineering Limit Detection (distinct from statistical deviations)
            crit_min, crit_max = limits.engineering_critical
            warn_min, warn_max = limits.engineering_warning
            if val < crit_min or val > crit_max:
                findings.append(
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
                findings.append(
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

            # B. Rate-of-Change Detection
            if len(window) >= 1:
                prev_ts, prev_val = window[-1]
                dt_seconds = (sample.timestamp - prev_ts).total_seconds()
                if dt_seconds > 0:
                    delta = val - prev_val
                    rate_per_sec = abs(delta) / dt_seconds
                    if rate_per_sec > limits.max_rate_per_sec:
                        severity: AlertSeverity = (
                            "CRITICAL" if rate_per_sec >= 2.0 * limits.max_rate_per_sec else "WARNING"
                        )
                        direction = "increased" if delta > 0 else "decreased"
                        findings.append(
                            AnomalyFinding(
                                satellite_id=sample.satellite_id,
                                sensor_name=sensor,
                                alert_type="RATE_OF_CHANGE",
                                severity=severity,
                                title=f"Rapid {sensor} rate-of-change detected",
                                description=(
                                    f"{self._human_name(sensor)} {direction} faster than the configured "
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
                                    "dt_seconds": round(dt_seconds, 4),
                                    "rate_per_sec": round(rate_per_sec, 4),
                                    "max_rate_per_sec": limits.max_rate_per_sec,
                                    "unit": limits.unit,
                                },
                                detected_at=sample.timestamp,
                            )
                        )

            # C. Rolling Baseline + Z-score Detection (only with sufficient baseline & meaningful std)
            if len(window) >= self.config.min_baseline_samples:
                series = pd.Series([v for _, v in window], dtype="float64")
                baseline_mean = float(series.mean())
                baseline_std = float(series.std(ddof=1))

                if (
                    math.isfinite(baseline_std)
                    and baseline_std >= limits.min_meaningful_std
                    and abs(val - baseline_mean) >= limits.min_deviation_deadband
                ):
                    z_score = (val - baseline_mean) / baseline_std
                    abs_z = abs(z_score)
                    if abs_z >= self.config.z_score_warning:
                        z_severity: AlertSeverity = (
                            "CRITICAL" if abs_z >= self.config.z_score_critical else "WARNING"
                        )
                        direction_word = "above" if z_score > 0 else "below"
                        two_tailed_p = float(2.0 * stats.norm.sf(abs_z))
                        findings.append(
                            AnomalyFinding(
                                satellite_id=sample.satellite_id,
                                sensor_name=sensor,
                                alert_type="STATISTICAL_ANOMALY",
                                severity=z_severity,
                                title=f"Statistical deviation detected on {sensor}",
                                description=(
                                    f"{self._human_name(sensor)} is {abs_z:.2f} standard deviations "
                                    f"{direction_word} its rolling baseline ({baseline_mean:.3f} ± "
                                    f"{baseline_std:.3f} {limits.unit})."
                                ),
                                observed_value=val,
                                expected_range=(
                                    f"{baseline_mean:.3f} ± "
                                    f"{self.config.z_score_warning * baseline_std:.3f} {limits.unit}"
                                ),
                                z_score=round(z_score, 4),
                                reason_code="Z_SCORE_DEVIATION",
                                evidence={
                                    "observed_value": val,
                                    "rolling_mean": round(baseline_mean, 4),
                                    "rolling_std": round(baseline_std, 4),
                                    "window_samples": len(window),
                                    "z_score": round(z_score, 4),
                                    "z_threshold_warning": self.config.z_score_warning,
                                    "z_threshold_critical": self.config.z_score_critical,
                                    "illustrative_two_tailed_p": round(two_tailed_p, 8),
                                    "unit": limits.unit,
                                },
                                detected_at=sample.timestamp,
                            )
                        )

            # Update rolling baseline window after evaluating incoming value
            window.append((sample.timestamp, val))

        return findings

    @staticmethod
    def _human_name(sensor_name: str) -> str:
        return sensor_name.replace("_", " ").capitalize()
