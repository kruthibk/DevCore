"""Detection pipeline integrating sensor integrity, statistical anomaly detection, and alerts."""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, sessionmaker

from app.core.detection_config import DetectionConfig
from app.core.fault_graph_config import DEFAULT_CORRELATION_WINDOW_SECONDS
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.realtime.socket_manager import (
    emit_alert_new,
    emit_alert_updated,
    emit_correlation_new,
    emit_correlation_updated,
    emit_detection_status,
    emit_fault_graph_update,
    emit_integrity_issue,
    register_detection_status_provider,
)
from app.schemas.alerts import (
    AlertRead,
    AlertType,
    DetectionConfigResponse,
    DetectionStatusResponse,
    SensorIntegrityFinding,
    SensorLimitsSchema,
)
from app.schemas.fault_graph import CorrelationRead, FaultGraphResponse
from app.schemas.telemetry import TelemetrySampleSchema
from app.services.alert_service import AlertCandidate, AlertService
from app.services.anomaly_detector import AnomalyFinding, StatisticalAnomalyDetector
from app.services.correlation_engine import CorrelationService
from app.services.sensor_integrity_service import SensorIntegrityService

logger = get_logger(__name__)

INTEGRITY_ALERT_TYPE_MAP: Dict[str, AlertType] = {
    "MISSING": "SENSOR_MISSING",
    "FROZEN": "SENSOR_FROZEN",
    "INVALID": "SENSOR_INVALID",
    "STALE": "SENSOR_STALE",
}


class DetectionPipelineService:
    """Coordinates integrity checks, statistical detection, DB alert persistence, and Socket.IO."""

    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        config: Optional[DetectionConfig] = None,
    ) -> None:
        self._session_factory: Callable[[], Session] = session_factory
        self.config = config or DetectionConfig()
        self.integrity_service = SensorIntegrityService(config=self.config)
        self.anomaly_detector = StatisticalAnomalyDetector(config=self.config)

        self._lock = asyncio.Lock()
        self.simulator_running: bool = False
        self.last_processed_at: Optional[datetime] = None
        self.processed_sample_count: int = 0
        self.persisted_alerts_count: int = 0
        self.failed_persist_count: int = 0
        self.last_persistence_error: Optional[str] = None
        self._cached_active_alert_count: int = 0

    def _to_alert_candidates(
        self,
        integrity_findings: List[SensorIntegrityFinding],
        anomaly_findings: List[AnomalyFinding],
    ) -> List[AlertCandidate]:
        candidates: List[AlertCandidate] = []

        for finding in integrity_findings:
            alert_type: AlertType = INTEGRITY_ALERT_TYPE_MAP[finding.integrity_status]
            candidates.append(
                AlertCandidate(
                    satellite_id=finding.satellite_id,
                    sensor_name=finding.sensor_name,
                    alert_type=alert_type,
                    severity=finding.severity,
                    title=f"Sensor integrity issue ({finding.integrity_status}) on {finding.sensor_name}",
                    description=finding.reason,
                    observed_value=finding.observed_value,
                    expected_range=None,
                    z_score=None,
                    reason_code=finding.reason_code,
                    evidence=finding.evidence,
                    detected_at=finding.detected_at,
                )
            )

        for anomaly in anomaly_findings:
            candidates.append(
                AlertCandidate(
                    satellite_id=anomaly.satellite_id,
                    sensor_name=anomaly.sensor_name,
                    alert_type=anomaly.alert_type,
                    severity=anomaly.severity,
                    title=anomaly.title,
                    description=anomaly.description,
                    observed_value=anomaly.observed_value,
                    expected_range=anomaly.expected_range,
                    z_score=anomaly.z_score,
                    reason_code=anomaly.reason_code,
                    evidence=anomaly.evidence,
                    detected_at=anomaly.detected_at,
                )
            )

        return candidates

    def _persist_candidates_sync(
        self,
        candidates: List[AlertCandidate],
        recovered_by_sat: Dict[str, List[str]],
        resolved_at: datetime,
    ) -> Tuple[
        List[AlertRead],
        List[AlertRead],
        int,
        List[CorrelationRead],
        List[CorrelationRead],
        Optional[FaultGraphResponse],
    ]:
        session = self._session_factory()
        try:
            created: List[AlertRead] = []
            updated: List[AlertRead] = []

            if candidates:
                c_list, u_list = AlertService.upsert_findings(
                    db=session,
                    candidates=candidates,
                    cooldown_seconds=self.config.dedup_cooldown_seconds,
                )
                created.extend(c_list)
                updated.extend(u_list)

            if self.config.auto_resolve_on_recovery:
                for sat_id, sensors in recovered_by_sat.items():
                    resolved_list = AlertService.resolve_recovered_alerts(
                        db=session,
                        satellite_id=sat_id,
                        sensor_names=sensors,
                        resolved_at=resolved_at,
                    )
                    updated.extend(resolved_list)

            corr_created: List[CorrelationRead] = []
            corr_updated: List[CorrelationRead] = []
            graph_snapshot: Optional[FaultGraphResponse] = None

            if created or updated:
                sat_ids = sorted({a.satellite_id for a in created + updated})
                for sat_id in sat_ids:
                    c_corr, u_corr = CorrelationService.correlate_and_persist(
                        db=session,
                        satellite_id=sat_id,
                        window_seconds=DEFAULT_CORRELATION_WINDOW_SECONDS,
                        reference_time=resolved_at,
                    )
                    corr_created.extend(c_corr)
                    corr_updated.extend(u_corr)
                if sat_ids:
                    graph_snapshot = CorrelationService.build_fault_graph(
                        db=session,
                        satellite_id=sat_ids[0],
                        window_seconds=DEFAULT_CORRELATION_WINDOW_SECONDS,
                    )

            summary = AlertService.get_summary_counts(db=session)
            return (
                created,
                updated,
                summary.active + summary.acknowledged,
                corr_created,
                corr_updated,
                graph_snapshot,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _query_open_alert_count_sync(self) -> int:
        session = self._session_factory()
        try:
            summary = AlertService.get_summary_counts(db=session)
            return summary.active + summary.acknowledged
        finally:
            session.close()

    async def refresh_active_alert_count(self) -> int:
        """Refresh active+acknowledged alert count safely from DB."""
        try:
            count = await asyncio.to_thread(self._query_open_alert_count_sync)
            self._cached_active_alert_count = count
        except Exception as exc:
            logger.warning("Unable to refresh open alert count", extra={"error": str(exc)})
        return self._cached_active_alert_count

    async def process_batch(
        self,
        samples: List[TelemetrySampleSchema],
        simulator_running: bool = True,
    ) -> Tuple[List[AlertRead], List[AlertRead], List[SensorIntegrityFinding]]:
        """Run integrity + statistical checks on an incoming telemetry batch without blocking ASGI."""
        async with self._lock:
            self.simulator_running = simulator_running
            if not samples:
                return [], [], []

            integrity_findings, valid_samples = self.integrity_service.evaluate_batch(
                samples=samples,
                simulator_running=simulator_running,
            )
            anomaly_findings = self.anomaly_detector.evaluate_batch(valid_samples)

            self.processed_sample_count += len(samples)
            batch_ts = max(
                (s.timestamp for s in samples if s.timestamp is not None),
                default=datetime.now(timezone.utc),
            )
            self.last_processed_at = batch_ts

            candidates = self._to_alert_candidates(integrity_findings, anomaly_findings)

            # Determine which channels have met recovery criteria (both integrity OK and clean streak)
            recovered_by_sat: Dict[str, List[str]] = {}
            if self.config.auto_resolve_on_recovery:
                satellite_ids = {s.satellite_id for s in samples}
                for sat_id in satellite_ids:
                    clean_integrity = self.integrity_service.get_clean_channels(satellite_id=sat_id)
                    clean_stats = set(
                        self.anomaly_detector.get_recovered_channels(
                            satellite_id=sat_id,
                            required_clean=self.config.recovery_consecutive_samples,
                        )
                    )
                    recovered = sorted(clean_integrity & clean_stats)
                    if recovered:
                        recovered_by_sat[sat_id] = recovered

            created: List[AlertRead] = []
            updated: List[AlertRead] = []
            corr_created: List[CorrelationRead] = []
            corr_updated: List[CorrelationRead] = []
            graph_snapshot: Optional[FaultGraphResponse] = None

            if candidates or (recovered_by_sat and self._cached_active_alert_count > 0):
                try:
                    (
                        created,
                        updated,
                        open_count,
                        corr_created,
                        corr_updated,
                        graph_snapshot,
                    ) = await asyncio.to_thread(
                        self._persist_candidates_sync,
                        candidates,
                        recovered_by_sat,
                        batch_ts,
                    )
                    self._cached_active_alert_count = open_count
                    self.persisted_alerts_count += len(created) + len(updated)
                    self.last_persistence_error = None
                except Exception as exc:
                    self.failed_persist_count += 1
                    self.last_persistence_error = str(exc)
                    logger.error(
                        "Failed to persist detection alerts; alerts not claimed persisted",
                        extra={"candidate_count": len(candidates), "error": str(exc)},
                    )
                    created = []
                    updated = []
                    corr_created = []
                    corr_updated = []
                    graph_snapshot = None

            status_snapshot = self.build_status()

        for finding in integrity_findings:
            await emit_integrity_issue(finding.model_dump(mode="json"))

        for alert in created:
            await emit_alert_new(alert.model_dump(mode="json"))

        for alert in updated:
            await emit_alert_updated(alert.model_dump(mode="json"))

        for corr in corr_created:
            await emit_correlation_new(corr.model_dump(mode="json"))

        for corr in corr_updated:
            await emit_correlation_updated(corr.model_dump(mode="json"))

        if graph_snapshot is not None:
            await emit_fault_graph_update(graph_snapshot.model_dump(mode="json"))

        await emit_detection_status(status_snapshot.model_dump(mode="json"))
        return created, updated, integrity_findings

    async def evaluate_staleness_tick(
        self,
        now: Optional[datetime] = None,
        simulator_running: bool = True,
    ) -> List[SensorIntegrityFinding]:
        """Run staleness check when simulator is running; mark inactive when stopped."""
        async with self._lock:
            self.simulator_running = simulator_running
            findings = self.integrity_service.evaluate_staleness(
                now=now,
                simulator_running=simulator_running,
            )
            if findings:
                candidates = self._to_alert_candidates(findings, [])
                try:
                    created, updated, open_count, corr_created, corr_updated, graph_snapshot = await asyncio.to_thread(
                        self._persist_candidates_sync,
                        candidates,
                        {},
                        now or datetime.now(timezone.utc),
                    )
                    self._cached_active_alert_count = open_count
                    self.persisted_alerts_count += len(created) + len(updated)
                    self.last_persistence_error = None
                except Exception as exc:
                    self.failed_persist_count += 1
                    self.last_persistence_error = str(exc)
                    created, updated, corr_created, corr_updated, graph_snapshot = [], [], [], [], None
            else:
                created, updated, corr_created, corr_updated, graph_snapshot = [], [], [], [], None
            status_snapshot = self.build_status()

        for finding in findings:
            await emit_integrity_issue(finding.model_dump(mode="json"))
        for alert in created:
            await emit_alert_new(alert.model_dump(mode="json"))
        for alert in updated:
            await emit_alert_updated(alert.model_dump(mode="json"))
        for corr in corr_created:
            await emit_correlation_new(corr.model_dump(mode="json"))
        for corr in corr_updated:
            await emit_correlation_updated(corr.model_dump(mode="json"))
        if graph_snapshot is not None:
            await emit_fault_graph_update(graph_snapshot.model_dump(mode="json"))
        await emit_detection_status(status_snapshot.model_dump(mode="json"))
        return findings

    async def on_simulator_stopped(self) -> None:
        """Update integrity states cleanly when simulator stops (never mark sensors stale)."""
        await self.evaluate_staleness_tick(simulator_running=False)

    def build_status(self, db: Optional[Session] = None) -> DetectionStatusResponse:
        """Build current detection engine and sensor channel health snapshot."""
        if db is not None:
            try:
                summary = AlertService.get_summary_counts(db=db)
                self._cached_active_alert_count = summary.active + summary.acknowledged
            except Exception as exc:
                logger.warning("Unable to query alert count for detection status", extra={"error": str(exc)})

        baseline_stats = self.anomaly_detector.get_baseline_summary()
        channels = self.integrity_service.get_channel_snapshots(
            simulator_running=self.simulator_running,
            baseline_stats=baseline_stats,
        )
        integrity_issues = sum(
            1
            for ch in channels
            if ch.integrity_status in ("MISSING", "FROZEN", "INVALID", "STALE")
        )

        return DetectionStatusResponse(
            engine_active=True,
            stream_state="ACTIVE" if self.simulator_running else "STREAM_INACTIVE",
            simulator_running=self.simulator_running,
            last_processed_at=self.last_processed_at,
            processed_sample_count=self.processed_sample_count,
            active_alert_count=self._cached_active_alert_count,
            integrity_issue_count=integrity_issues,
            persisted_alerts_count=self.persisted_alerts_count,
            failed_persist_count=self.failed_persist_count,
            last_persistence_error=self.last_persistence_error,
            sensor_states=channels,
            config_summary={
                "rolling_window_size": self.config.rolling_window_size,
                "min_baseline_samples": self.config.min_baseline_samples,
                "z_score_warning": self.config.z_score_warning,
                "z_score_critical": self.config.z_score_critical,
                "frozen_consecutive_samples": self.config.frozen_consecutive_samples,
                "stale_timeout_seconds": self.config.stale_timeout_seconds,
                "dedup_cooldown_seconds": self.config.dedup_cooldown_seconds,
                "recovery_consecutive_samples": self.config.recovery_consecutive_samples,
            },
            timestamp=datetime.now(timezone.utc),
        )

    def build_config_response(self) -> DetectionConfigResponse:
        """Return serialized read-only detection thresholds and sensor limits."""
        limits_map = {
            sensor: SensorLimitsSchema(
                unit=lim.unit,
                engineering_warning=list(lim.engineering_warning),
                engineering_critical=list(lim.engineering_critical),
                physical_valid_range=list(lim.physical_valid_range),
                max_rate_per_sec=lim.max_rate_per_sec,
                min_meaningful_std=lim.min_meaningful_std,
            )
            for sensor, lim in self.config.sensor_limits.items()
        }
        return DetectionConfigResponse(
            rolling_window_size=self.config.rolling_window_size,
            min_baseline_samples=self.config.min_baseline_samples,
            z_score_warning=self.config.z_score_warning,
            z_score_critical=self.config.z_score_critical,
            frozen_consecutive_samples=self.config.frozen_consecutive_samples,
            stale_timeout_seconds=self.config.stale_timeout_seconds,
            dedup_cooldown_seconds=self.config.dedup_cooldown_seconds,
            recovery_consecutive_samples=self.config.recovery_consecutive_samples,
            sensor_limits=limits_map,
        )


detection_pipeline = DetectionPipelineService()


async def _provide_detection_status() -> dict:
    await detection_pipeline.refresh_active_alert_count()
    return detection_pipeline.build_status().model_dump(mode="json")


register_detection_status_provider(_provide_detection_status)
