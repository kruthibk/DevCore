"""Cross-signal sensor integrity verification service."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Deque, Dict, List, Optional, Tuple

from app.core.detection_config import DetectionConfig
from app.schemas.alerts import IntegrityStatus, SensorChannelHealth, SensorIntegrityFinding
from app.schemas.telemetry import SENSOR_UNITS, TelemetrySampleSchema
from app.services.telemetry_generator import SUPPORTED_SENSORS


@dataclass
class _SensorIntegrityState:
    last_received_at: Optional[datetime] = None
    last_value: Optional[float] = None
    status: IntegrityStatus = "NO_DATA"
    issue_reason: Optional[str] = None
    recent_values: Deque[float] = field(default_factory=lambda: deque(maxlen=20))


class SensorIntegrityService:
    """Detects MISSING, FROZEN, INVALID, and STALE sensor conditions independently."""

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        self.config = config or DetectionConfig()
        self._states: Dict[str, _SensorIntegrityState] = {
            sensor: _SensorIntegrityState(
                recent_values=deque(maxlen=self.config.frozen_consecutive_samples)
            )
            for sensor in SUPPORTED_SENSORS
        }

    def evaluate_batch(
        self,
        samples: List[TelemetrySampleSchema],
        simulator_running: bool = True,
    ) -> Tuple[List[SensorIntegrityFinding], List[TelemetrySampleSchema]]:
        """Evaluate incoming telemetry samples for integrity defects.

        Does NOT read sample.quality_status; inspects only raw values and timestamps.
        Returns (integrity_findings, valid_numeric_samples_for_statistical_detection).
        """
        findings: List[SensorIntegrityFinding] = []
        valid_samples: List[TelemetrySampleSchema] = []

        for sample in samples:
            sensor = sample.sensor_name
            state = self._states.setdefault(
                sensor,
                _SensorIntegrityState(
                    recent_values=deque(maxlen=self.config.frozen_consecutive_samples)
                ),
            )
            limits = self.config.sensor_limits.get(sensor)

            # 1. Timestamp validity check
            ts = sample.timestamp
            if ts is None or ts.tzinfo is None:
                detected_at = datetime.now(timezone.utc)
                state.status = "INVALID"
                state.issue_reason = "Timestamp missing or lacks timezone awareness."
                findings.append(
                    SensorIntegrityFinding(
                        satellite_id=sample.satellite_id,
                        sensor_name=sensor,
                        integrity_status="INVALID",
                        severity="CRITICAL",
                        observed_value=sample.sensor_value if self._is_finite(sample.sensor_value) else None,
                        detected_at=detected_at,
                        reason_code="INVALID_TIMESTAMP",
                        reason=f"Telemetry timestamp for {sensor} is missing or not timezone-aware.",
                        evidence={"raw_timestamp": str(ts)},
                    )
                )
                continue

            # 2. MISSING reading check
            if sample.sensor_value is None:
                state.last_received_at = ts
                state.last_value = None
                state.recent_values.clear()
                state.status = "MISSING"
                state.issue_reason = f"Missing or null reading received from {sensor}."
                findings.append(
                    SensorIntegrityFinding(
                        satellite_id=sample.satellite_id,
                        sensor_name=sensor,
                        integrity_status="MISSING",
                        severity="WARNING",
                        observed_value=None,
                        detected_at=ts,
                        reason_code="SENSOR_VALUE_MISSING",
                        reason=f"Missing or null reading received from {sensor} at {ts.isoformat()}.",
                        evidence={"expected_unit": sample.unit, "timestamp": ts.isoformat()},
                    )
                )
                continue

            # 3. INVALID (non-finite or outside physical valid range)
            val = float(sample.sensor_value)
            if not math.isfinite(val):
                state.last_received_at = ts
                state.last_value = None
                state.recent_values.clear()
                state.status = "INVALID"
                state.issue_reason = f"Non-finite value ({val}) reported by {sensor}."
                findings.append(
                    SensorIntegrityFinding(
                        satellite_id=sample.satellite_id,
                        sensor_name=sensor,
                        integrity_status="INVALID",
                        severity="CRITICAL",
                        observed_value=None,
                        detected_at=ts,
                        reason_code="NON_FINITE_READING",
                        reason=f"Non-finite value reported by {sensor}.",
                        evidence={"raw_value": str(val), "timestamp": ts.isoformat()},
                    )
                )
                continue

            if limits is not None:
                phys_min, phys_max = limits.physical_valid_range
                if val < phys_min or val > phys_max:
                    state.last_received_at = ts
                    state.last_value = val
                    state.recent_values.clear()
                    state.status = "INVALID"
                    state.issue_reason = (
                        f"Value {val} {sample.unit} is outside physical sensor range [{phys_min}, {phys_max}]."
                    )
                    findings.append(
                        SensorIntegrityFinding(
                            satellite_id=sample.satellite_id,
                            sensor_name=sensor,
                            integrity_status="INVALID",
                            severity="CRITICAL",
                            observed_value=val,
                            detected_at=ts,
                            reason_code="OUT_OF_PHYSICAL_RANGE",
                            reason=state.issue_reason,
                            evidence={
                                "observed_value": val,
                                "physical_min": phys_min,
                                "physical_max": phys_max,
                                "unit": sample.unit,
                            },
                        )
                    )
                    continue

            # Sample is finite and physically plausible
            state.last_received_at = ts
            state.last_value = val
            state.recent_values.append(val)
            valid_samples.append(sample)

            # 4. FROZEN sensor check across consecutive samples
            required_n = self.config.frozen_consecutive_samples
            if len(state.recent_values) >= required_n:
                first_val = state.recent_values[0]
                is_frozen = all(
                    abs(v - first_val) <= self.config.frozen_tolerance
                    for v in state.recent_values
                )
                if is_frozen:
                    state.status = "FROZEN"
                    state.issue_reason = (
                        f"The {sensor} sensor produced repeated identical readings ({val} {sample.unit}) "
                        f"across {len(state.recent_values)} consecutive samples."
                    )
                    findings.append(
                        SensorIntegrityFinding(
                            satellite_id=sample.satellite_id,
                            sensor_name=sensor,
                            integrity_status="FROZEN",
                            severity="WARNING",
                            observed_value=val,
                            detected_at=ts,
                            reason_code="REPEATED_IDENTICAL_VALUES",
                            reason=state.issue_reason,
                            evidence={
                                "repeated_value": val,
                                "consecutive_samples": len(state.recent_values),
                                "unit": sample.unit,
                            },
                        )
                    )
                    continue

            state.status = "OK"
            state.issue_reason = None

        # Mark inactive stream cleanly if simulator is not running
        if not simulator_running:
            for state in self._states.values():
                if state.status == "OK":
                    state.status = "STREAM_INACTIVE"

        return findings, valid_samples

    def evaluate_staleness(
        self,
        now: Optional[datetime] = None,
        satellite_id: str = "SAT-01",
        simulator_running: bool = True,
    ) -> List[SensorIntegrityFinding]:
        """Check for stale sensors ONLY when the telemetry stream is actively running."""
        ref_now = now or datetime.now(timezone.utc)
        findings: List[SensorIntegrityFinding] = []

        if not simulator_running:
            for state in self._states.values():
                if state.status in ("OK", "STALE"):
                    state.status = "STREAM_INACTIVE"
                    state.issue_reason = "Telemetry stream is inactive (simulator stopped)."
            return findings

        timeout = self.config.stale_timeout_seconds
        for sensor, state in self._states.items():
            if state.last_received_at is None:
                continue
            elapsed = (ref_now - state.last_received_at).total_seconds()
            if elapsed > timeout:
                state.status = "STALE"
                state.issue_reason = (
                    f"No new readings received from the {sensor} sensor within {timeout:.1f}s "
                    f"(elapsed: {elapsed:.1f}s)."
                )
                findings.append(
                    SensorIntegrityFinding(
                        satellite_id=satellite_id,
                        sensor_name=sensor,
                        integrity_status="STALE",
                        severity="WARNING",
                        observed_value=state.last_value,
                        detected_at=ref_now,
                        reason_code="SENSOR_UPDATE_TIMEOUT",
                        reason=state.issue_reason,
                        evidence={
                            "last_received_at": state.last_received_at.isoformat(),
                            "elapsed_seconds": round(elapsed, 2),
                            "timeout_seconds": timeout,
                        },
                    )
                )

        return findings

    def get_channel_snapshots(
        self,
        simulator_running: bool,
        baseline_stats: Optional[Dict[str, Tuple[int, Optional[float], Optional[float]]]] = None,
    ) -> List[SensorChannelHealth]:
        """Return current integrity and baseline summary for all supported sensors."""
        snapshots: List[SensorChannelHealth] = []
        for sensor in SUPPORTED_SENSORS:
            state = self._states.get(sensor, _SensorIntegrityState())
            status_val: IntegrityStatus = state.status
            reason = state.issue_reason

            if not simulator_running and status_val in ("OK", "NO_DATA", "STALE"):
                status_val = "STREAM_INACTIVE"
                reason = "Telemetry stream inactive (simulator stopped)."

            count, mean_val, std_val = (
                baseline_stats.get(sensor, (0, None, None))
                if baseline_stats is not None
                else (0, None, None)
            )
            snapshots.append(
                SensorChannelHealth(
                    sensor_name=sensor,
                    unit=SENSOR_UNITS.get(sensor, ""),
                    integrity_status=status_val,
                    last_received_at=state.last_received_at,
                    last_value=state.last_value,
                    baseline_samples=count,
                    baseline_mean=mean_val,
                    baseline_std=std_val,
                    issue_reason=reason,
                )
            )
        return snapshots

    @staticmethod
    def _is_finite(value: Optional[float]) -> bool:
        return value is not None and math.isfinite(float(value))
