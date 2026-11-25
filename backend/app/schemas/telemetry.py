"""Pydantic schemas for telemetry simulator, fault injection, and history APIs."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SYNTHETIC_DATA_ORIGIN = "SYNTHETIC SIMULATION DATA"

SensorName = Literal["battery_voltage", "temperature", "roll", "pitch", "yaw"]
FaultType = Literal[
    "battery_drop",
    "temperature_spike",
    "attitude_disturbance",
    "frozen_sensor",
    "missing_data",
]
QualityStatus = Literal["NOMINAL", "FAULT_SIMULATED", "FROZEN", "MISSING"]

SENSOR_UNITS: dict[str, str] = {
    "battery_voltage": "V",
    "temperature": "°C",
    "roll": "degrees",
    "pitch": "degrees",
    "yaw": "degrees",
}


class ActiveFault(BaseModel):
    """Represents a currently active synthetic fault scenario."""

    fault_type: FaultType
    target_sensor: Optional[SensorName] = None
    activated_at: datetime


class SimulatorStartRequest(BaseModel):
    """Optional configuration when starting the telemetry simulator."""

    interval_seconds: Optional[float] = Field(default=None, ge=0.2, le=60.0)


class FaultInjectRequest(BaseModel):
    """Request body for activating a synthetic fault scenario."""

    fault_type: FaultType
    target_sensor: Optional[SensorName] = None

    @model_validator(mode="after")
    def validate_target_sensor(self) -> "FaultInjectRequest":
        if self.fault_type in ("frozen_sensor", "missing_data") and self.target_sensor is None:
            # Default cleanly to temperature if operator activates without specifying sensor
            self.target_sensor = "temperature"
        if self.fault_type not in ("frozen_sensor", "missing_data") and self.target_sensor is not None:
            raise ValueError(
                f"target_sensor is only supported for frozen_sensor and missing_data, not {self.fault_type}"
            )
        return self


class SimulatorStatusResponse(BaseModel):
    """Current simulator runtime, fault, and persistence counters."""

    running: bool
    satellite_id: str
    interval_seconds: float
    data_origin: str = SYNTHETIC_DATA_ORIGIN
    active_faults: list[ActiveFault]
    generated_count: int
    streamed_count: int
    persisted_count: int
    pending_persist_count: int
    failed_persist_batches: int
    last_persistence_error: Optional[str] = None
    last_generated_at: Optional[datetime] = None
    timestamp: datetime


class FaultActionResponse(BaseModel):
    """Response for fault activation or clearing."""

    action: Literal["activated", "cleared"]
    data_origin: str = SYNTHETIC_DATA_ORIGIN
    fault_type: Optional[FaultType] = None
    target_sensor: Optional[SensorName] = None
    active_faults: list[ActiveFault]
    timestamp: datetime


class TelemetrySampleSchema(BaseModel):
    """Single sensor reading payload (streamed or stored)."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    satellite_id: str
    sensor_name: SensorName
    sensor_value: Optional[float]
    unit: str
    timestamp: datetime
    quality_status: QualityStatus


class TelemetryLatestResponse(BaseModel):
    """Response for GET /api/v1/telemetry/latest."""

    satellite_id: str
    data_origin: str = SYNTHETIC_DATA_ORIGIN
    simulator_running: bool
    readings: dict[str, TelemetrySampleSchema]
    timestamp: datetime


class TelemetryHistoryResponse(BaseModel):
    """Paginated historical telemetry response."""

    satellite_id: str
    data_origin: str = SYNTHETIC_DATA_ORIGIN
    total: int
    limit: int
    offset: int
    items: list[TelemetrySampleSchema]
