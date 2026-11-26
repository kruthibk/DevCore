"""Async telemetry simulation orchestrator, Socket.IO broadcaster, and DB batch persister."""

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, List, Optional

from fastapi import status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.telemetry import TelemetryReading
from app.realtime.socket_manager import (
    emit_detection_status,
    emit_simulation_fault,
    emit_simulation_status,
    emit_telemetry_update,
    register_status_provider,
)
from app.schemas.telemetry import (
    SYNTHETIC_DATA_ORIGIN,
    FaultActionResponse,
    FaultType,
    SensorName,
    SimulatorStatusResponse,
    TelemetryLatestResponse,
    TelemetrySampleSchema,
)
from app.services.detection_pipeline import DetectionPipelineService, detection_pipeline
from app.services.telemetry_generator import SUPPORTED_SENSORS, TelemetryGenerator

logger = get_logger(__name__)


class SimulatorAlreadyRunningError(AppException):
    """Raised when attempting to start a simulator that is already active."""

    def __init__(self) -> None:
        super().__init__(
            message="Telemetry simulator is already running.",
            code="SIMULATOR_ALREADY_RUNNING",
            status_code=status.HTTP_409_CONFLICT,
        )


class TelemetrySimulatorService:
    """Manages synthetic telemetry generation, streaming, and bounded batch persistence."""

    def __init__(
        self,
        session_factory: sessionmaker = SessionLocal,
        seed: Optional[int] = None,
        detection_service: Optional[DetectionPipelineService] = None,
    ) -> None:
        settings = get_settings()
        self._session_factory: Callable[[], Session] = session_factory
        self._detection_service = detection_service
        self._satellite_id = settings.simulator_satellite_id
        self._interval_seconds = settings.simulator_interval_seconds
        self._persist_batch_size = settings.simulator_persist_batch_size

        self._generator = TelemetryGenerator(
            satellite_id=self._satellite_id,
            nominal_voltage=settings.simulator_nominal_voltage,
            nominal_temperature=settings.simulator_nominal_temperature,
            seed=seed,
        )

        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task[None]] = None
        self._staleness_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

        self._latest_readings: Dict[str, TelemetrySampleSchema] = {}
        self._pending_batch: Deque[TelemetrySampleSchema] = deque(maxlen=500)

        self.generated_count = 0
        self.streamed_count = 0
        self.persisted_count = 0
        self.failed_persist_batches = 0
        self.last_persistence_error: Optional[str] = None
        self.last_generated_at: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        """Return True when the background simulation task is active."""
        return self._task is not None and not self._task.done()

    def build_status(self) -> SimulatorStatusResponse:
        """Return a snapshot of simulator runtime, faults, and persistence counters."""
        return SimulatorStatusResponse(
            running=self.is_running,
            satellite_id=self._satellite_id,
            interval_seconds=self._interval_seconds,
            data_origin=SYNTHETIC_DATA_ORIGIN,
            active_faults=self._generator.get_active_faults(),
            generated_count=self.generated_count,
            streamed_count=self.streamed_count,
            persisted_count=self.persisted_count,
            pending_persist_count=len(self._pending_batch),
            failed_persist_batches=self.failed_persist_batches,
            last_persistence_error=self.last_persistence_error,
            last_generated_at=self.last_generated_at,
            timestamp=datetime.now(timezone.utc),
        )

    async def start(self, interval_seconds: Optional[float] = None) -> SimulatorStatusResponse:
        """Start the background telemetry simulator loop if not already running."""
        async with self._lock:
            if self.is_running:
                raise SimulatorAlreadyRunningError()

            if interval_seconds is not None:
                self._interval_seconds = interval_seconds

            self._stop_event.clear()
            self._task = asyncio.create_task(self._simulation_loop(), name="sat-triage-simulator")
            if self._detection_service is not None:
                self._staleness_task = asyncio.create_task(
                    self._staleness_loop(),
                    name="sat-triage-staleness-watchdog",
                )
            snapshot = self.build_status()

        logger.info(
            "Telemetry simulator started",
            extra={
                "satellite_id": self._satellite_id,
                "interval_seconds": self._interval_seconds,
            },
        )
        await emit_simulation_status(snapshot.model_dump(mode="json"))
        if self._detection_service is not None:
            self._detection_service.simulator_running = True
            await emit_detection_status(self._detection_service.build_status().model_dump(mode="json"))
        return snapshot

    async def stop(self) -> SimulatorStatusResponse:
        """Stop the simulator task gracefully and flush pending samples."""
        async with self._lock:
            task = self._task
            staleness_task = self._staleness_task
            self._stop_event.set()
            for bg_task in (task, staleness_task):
                if bg_task is not None and not bg_task.done():
                    try:
                        await asyncio.wait_for(bg_task, timeout=5.0)
                    except asyncio.TimeoutError:
                        bg_task.cancel()
                        try:
                            await bg_task
                        except asyncio.CancelledError:
                            pass
            self._task = None
            self._staleness_task = None
            await self.flush_pending_batch()
            snapshot = self.build_status()

        logger.info("Telemetry simulator stopped", extra={"satellite_id": self._satellite_id})
        await emit_simulation_status(snapshot.model_dump(mode="json"))
        if self._detection_service is not None:
            await self._detection_service.on_simulator_stopped()
        return snapshot

    async def stop_if_running(self) -> None:
        """Stop the simulator cleanly during application shutdown."""
        if self.is_running or len(self._pending_batch) > 0:
            await self.stop()

    async def inject_fault(
        self,
        fault_type: FaultType,
        target_sensor: Optional[SensorName] = None,
    ) -> FaultActionResponse:
        """Activate a fault scenario and broadcast status updates."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            self._generator.activate_fault(
                fault_type=fault_type,
                target_sensor=target_sensor,
                activated_at=now,
            )
            active_faults = self._generator.get_active_faults()
            status_snapshot = self.build_status()

        event_payload = FaultActionResponse(
            action="activated",
            fault_type=fault_type,
            target_sensor=target_sensor,
            active_faults=active_faults,
            timestamp=now,
        )
        logger.info(
            "Fault scenario activated",
            extra={"fault_type": fault_type, "target_sensor": target_sensor},
        )
        await emit_simulation_fault(event_payload.model_dump(mode="json"))
        await emit_simulation_status(status_snapshot.model_dump(mode="json"))
        return event_payload

    async def clear_faults(self) -> FaultActionResponse:
        """Clear all active fault scenarios and notify connected clients."""
        async with self._lock:
            now = datetime.now(timezone.utc)
            self._generator.clear_faults()
            status_snapshot = self.build_status()

        event_payload = FaultActionResponse(
            action="cleared",
            fault_type=None,
            target_sensor=None,
            active_faults=[],
            timestamp=now,
        )
        logger.info("All fault scenarios cleared")
        await emit_simulation_fault(event_payload.model_dump(mode="json"))
        await emit_simulation_status(status_snapshot.model_dump(mode="json"))
        return event_payload

    async def step_once(self) -> List[TelemetrySampleSchema]:
        """Generate one tick of telemetry, stream it, and trigger bounded batch persistence."""
        samples = self._generator.generate_tick()
        self.generated_count += len(samples)
        self.last_generated_at = samples[0].timestamp

        for sample in samples:
            self._latest_readings[sample.sensor_name] = sample
            self._pending_batch.append(sample)

        update_payload = {
            "satellite_id": self._satellite_id,
            "data_origin": SYNTHETIC_DATA_ORIGIN,
            "simulator_running": self.is_running,
            "timestamp": self.last_generated_at.isoformat(),
            "active_faults": [f.model_dump(mode="json") for f in self._generator.get_active_faults()],
            "generated_count": self.generated_count,
            "streamed_count": self.streamed_count + len(samples),
            "persisted_count": self.persisted_count,
            "last_persistence_error": self.last_persistence_error,
            "readings": [s.model_dump(mode="json") for s in samples],
        }
        await emit_telemetry_update(update_payload)
        self.streamed_count += len(samples)

        if len(self._pending_batch) >= self._persist_batch_size:
            await self.flush_pending_batch()

        if self._detection_service is not None:
            await self._detection_service.process_batch(samples, simulator_running=self.is_running)

        return samples

    async def flush_pending_batch(self) -> int:
        """Persist buffered telemetry samples in a single controlled DB transaction."""
        if not self._pending_batch:
            return 0

        batch = list(self._pending_batch)
        self._pending_batch.clear()

        try:
            inserted = await asyncio.to_thread(self._persist_rows_sync, batch)
            self.persisted_count += inserted
            self.last_persistence_error = None
            return inserted
        except Exception as exc:
            self.failed_persist_batches += 1
            self.last_persistence_error = str(exc)
            # Re-queue unsaved samples bounded by maxlen so transient DB blips do not lose frames
            for item in reversed(batch):
                if len(self._pending_batch) < (self._pending_batch.maxlen or 500):
                    self._pending_batch.appendleft(item)
            logger.error(
                "Telemetry batch persistence failed; records queued for retry",
                extra={"batch_size": len(batch), "error": str(exc)},
            )
            return 0

    def _persist_rows_sync(self, batch: List[TelemetrySampleSchema]) -> int:
        """Write a batch of telemetry samples to PostgreSQL inside a scoped session."""
        session = self._session_factory()
        try:
            orm_rows = [
                TelemetryReading(
                    satellite_id=item.satellite_id,
                    sensor_name=item.sensor_name,
                    sensor_value=item.sensor_value,
                    unit=item.unit,
                    timestamp=item.timestamp,
                    quality_status=item.quality_status,
                )
                for item in batch
            ]
            session.add_all(orm_rows)
            session.commit()
            return len(orm_rows)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def _simulation_loop(self) -> None:
        """Background loop executing synthetic telemetry ticks until stopped."""
        while not self._stop_event.is_set():
            try:
                await self.step_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Error in telemetry simulation tick", extra={"error": str(exc)})

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                continue

    async def _staleness_loop(self) -> None:
        """Periodic watchdog evaluating sensor staleness while the simulator is running."""
        check_interval = 1.5
        if self._detection_service is not None:
            check_interval = max(
                0.5,
                min(2.0, self._detection_service.config.stale_timeout_seconds / 2.0),
            )
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=check_interval)
                break
            except asyncio.TimeoutError:
                if self._detection_service is not None and self.is_running:
                    try:
                        await self._detection_service.evaluate_staleness_tick(
                            simulator_running=True
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        logger.warning(
                            "Periodic staleness check failed",
                            extra={"error": str(exc)},
                        )

    def get_latest_readings(
        self,
        db: Session,
        satellite_id: str = "SAT-01",
    ) -> TelemetryLatestResponse:
        """Return latest readings from memory buffer or database fallback."""
        readings: Dict[str, TelemetrySampleSchema] = {}
        if satellite_id == self._satellite_id and self._latest_readings:
            readings = dict(self._latest_readings)
        else:
            for sensor in SUPPORTED_SENSORS:
                row = db.execute(
                    select(TelemetryReading)
                    .where(
                        TelemetryReading.satellite_id == satellite_id,
                        TelemetryReading.sensor_name == sensor,
                    )
                    .order_by(desc(TelemetryReading.timestamp), desc(TelemetryReading.id))
                    .limit(1)
                ).scalar_one_or_none()
                if row is not None:
                    readings[sensor] = TelemetrySampleSchema.model_validate(row)

        return TelemetryLatestResponse(
            satellite_id=satellite_id,
            simulator_running=self.is_running,
            readings=readings,
            timestamp=datetime.now(timezone.utc),
        )

    def get_history(
        self,
        db: Session,
        satellite_id: str = "SAT-01",
        sensor_name: Optional[SensorName] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[TelemetrySampleSchema], int]:
        """Query persisted historical telemetry with filters and bounded pagination."""
        filters = [TelemetryReading.satellite_id == satellite_id]
        if sensor_name is not None:
            filters.append(TelemetryReading.sensor_name == sensor_name)
        if start_time is not None:
            filters.append(TelemetryReading.timestamp >= start_time)
        if end_time is not None:
            filters.append(TelemetryReading.timestamp <= end_time)

        total = db.execute(
            select(func.count()).select_from(TelemetryReading).where(*filters)
        ).scalar_one()

        rows = (
            db.execute(
                select(TelemetryReading)
                .where(*filters)
                .order_by(desc(TelemetryReading.timestamp), desc(TelemetryReading.id))
                .limit(limit)
                .offset(offset)
            )
            .scalars()
            .all()
        )
        return [TelemetrySampleSchema.model_validate(r) for r in rows], total


simulator_service = TelemetrySimulatorService(detection_service=detection_pipeline)


async def _provide_socket_status() -> dict:
    return simulator_service.build_status().model_dump(mode="json")


register_status_provider(_provide_socket_status)
