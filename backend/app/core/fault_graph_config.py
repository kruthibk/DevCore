"""Configurable satellite subsystem dependency graph and hybrid causal rules."""

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class SubsystemDefinition:
    """Represents a physical or logical spacecraft subsystem node."""

    id: str
    name: str
    description: str
    sensors: Tuple[str, ...]
    failure_modes: Tuple[str, ...]


@dataclass(frozen=True)
class DependencyEdgeDefinition:
    """Directed relationship between subsystems or sensors."""

    source: str
    target: str
    relationship: str
    description: str


@dataclass(frozen=True)
class CausalRuleDefinition:
    """Explicit domain rule mapping co-occurring alerts to a possible common cause."""

    rule_code: str
    suspected_subsystem: str
    title: str
    hypothesis_template: str
    required_sensors: Tuple[str, ...]
    min_alerts: int = 2
    requires_integrity_only: bool = False
    requires_physical_alerts: bool = False


SUBSYSTEM_DEFINITIONS: Dict[str, SubsystemDefinition] = {
    "EPS": SubsystemDefinition(
        id="EPS",
        name="Electrical Power System",
        description="Battery pack, solar array regulation, and spacecraft primary power bus.",
        sensors=("battery_voltage",),
        failure_modes=(
            "eps_bus_undervoltage",
            "eps_power_rail_ripple",
            "eps_solar_array_degradation",
        ),
    ),
    "THERMAL": SubsystemDefinition(
        id="THERMAL",
        name="Thermal Control System",
        description="Heaters, radiators, and internal payload thermal regulation deck.",
        sensors=("temperature",),
        failure_modes=(
            "thermal_overheating_excursion",
            "thermal_heater_stuck",
            "thermal_radiator_degradation",
        ),
    ),
    "ADCS": SubsystemDefinition(
        id="ADCS",
        name="Attitude Determination and Control System",
        description="Reaction wheels, star trackers, and 3-axis spacecraft orientation control.",
        sensors=("roll", "pitch", "yaw"),
        failure_modes=(
            "adcs_attitude_disturbance",
            "adcs_reaction_wheel_saturation",
            "adcs_pointing_loss",
        ),
    ),
    "OBC": SubsystemDefinition(
        id="OBC",
        name="Onboard Computer",
        description="Flight processor, telemetry bus scheduling, and command & data handling.",
        sensors=(),
        failure_modes=(
            "obc_telemetry_bus_stall",
            "obc_sampling_cadence_fault",
        ),
    ),
    "SENSORS": SubsystemDefinition(
        id="SENSORS",
        name="Sensors & Instrumentation",
        description="Transducers, ADC front-ends, and sensor signal conditioning.",
        sensors=("battery_voltage", "temperature", "roll", "pitch", "yaw"),
        failure_modes=(
            "sensor_channel_freeze",
            "sensor_telemetry_dropout",
            "sensor_calibration_invalid",
        ),
    ),
}

SENSOR_TO_PRIMARY_SUBSYSTEM: Dict[str, str] = {
    "battery_voltage": "EPS",
    "temperature": "THERMAL",
    "roll": "ADCS",
    "pitch": "ADCS",
    "yaw": "ADCS",
}

SUBSYSTEM_DEPENDENCY_EDGES: Tuple[DependencyEdgeDefinition, ...] = (
    DependencyEdgeDefinition(
        source="EPS",
        target="THERMAL",
        relationship="PROVIDES_POWER",
        description="EPS supplies regulated bus power to thermal heaters and cooling loops.",
    ),
    DependencyEdgeDefinition(
        source="EPS",
        target="ADCS",
        relationship="PROVIDES_POWER",
        description="EPS powers reaction wheels, magnetorquers, and ADCS avionics.",
    ),
    DependencyEdgeDefinition(
        source="EPS",
        target="OBC",
        relationship="PROVIDES_POWER",
        description="EPS supplies core voltage rails to the onboard flight computer.",
    ),
    DependencyEdgeDefinition(
        source="EPS",
        target="SENSORS",
        relationship="PROVIDES_POWER",
        description="EPS excites analog/digital sensor front-ends.",
    ),
    DependencyEdgeDefinition(
        source="THERMAL",
        target="EPS",
        relationship="THERMAL_COUPLING",
        description="Battery temperature excursions degrade discharge efficiency and bus voltage.",
    ),
    DependencyEdgeDefinition(
        source="THERMAL",
        target="ADCS",
        relationship="THERMAL_COUPLING",
        description="Thermal gradients can induce gyro bias drift and actuator stress.",
    ),
    DependencyEdgeDefinition(
        source="ADCS",
        target="EPS",
        relationship="ATTITUDE_SOLAR_COUPLING",
        description="Attitude off-pointing reduces solar array incidence and battery charging.",
    ),
    DependencyEdgeDefinition(
        source="ADCS",
        target="THERMAL",
        relationship="ATTITUDE_THERMAL_COUPLING",
        description="Attitude changes alter spacecraft solar illumination and radiator exposure.",
    ),
    DependencyEdgeDefinition(
        source="SENSORS",
        target="OBC",
        relationship="TELEMETRY_BUS",
        description="Sensors transmit sampled telemetry frames to OBC over the telemetry bus.",
    ),
    DependencyEdgeDefinition(
        source="OBC",
        target="ADCS",
        relationship="CONTROL_LOOP",
        description="OBC executes attitude estimation and actuator control cycles.",
    ),
)

CAUSAL_RULES: List[CausalRuleDefinition] = [
    CausalRuleDefinition(
        rule_code="EPS_THERMAL_COUPLED_FAULT",
        suspected_subsystem="EPS",
        title="Possible coupled EPS and Thermal subsystem anomaly",
        hypothesis_template=(
            "Co-occurring power (battery_voltage) and thermal (temperature) anomalies suggest a "
            "possible power-thermal coupling event (such as battery thermal stress or heater/bus load shift)."
        ),
        required_sensors=("battery_voltage", "temperature"),
        min_alerts=2,
        requires_physical_alerts=True,
    ),
    CausalRuleDefinition(
        rule_code="ADCS_EPS_SOLAR_COUPLING",
        suspected_subsystem="ADCS",
        title="Possible attitude-induced power coupling",
        hypothesis_template=(
            "Co-occurring attitude excursions and battery voltage drop suggest possible solar "
            "off-pointing or coupled ADCS/EPS power load disturbance."
        ),
        required_sensors=("battery_voltage", "roll", "pitch", "yaw"),
        min_alerts=2,
        requires_physical_alerts=True,
    ),
    CausalRuleDefinition(
        rule_code="OBC_MULTI_CHANNEL_INTEGRITY",
        suspected_subsystem="OBC",
        title="Possible OBC telemetry bus or sampling fault",
        hypothesis_template=(
            "Multiple sensor channels exhibited integrity defects within the same time window, "
            "indicating a possible onboard computer telemetry bus or acquisition cadence issue."
        ),
        required_sensors=(),
        min_alerts=2,
        requires_integrity_only=True,
    ),
    CausalRuleDefinition(
        rule_code="EPS_UNDERVOLTAGE_CLUSTER",
        suspected_subsystem="EPS",
        title="Possible Electrical Power System (EPS) voltage anomaly",
        hypothesis_template=(
            "Multiple independent detectors flagged battery_voltage within the correlation window, "
            "suggesting a possible EPS discharge, bus load spike, or regulation fault."
        ),
        required_sensors=("battery_voltage",),
        min_alerts=2,
        requires_physical_alerts=True,
    ),
    CausalRuleDefinition(
        rule_code="THERMAL_EXCURSION_CLUSTER",
        suspected_subsystem="THERMAL",
        title="Possible Thermal Control System excursion",
        hypothesis_template=(
            "Multiple detectors flagged temperature excursions within the correlation window, "
            "suggesting a possible thermal control imbalance, heater fault, or radiator degradation."
        ),
        required_sensors=("temperature",),
        min_alerts=2,
        requires_physical_alerts=True,
    ),
    CausalRuleDefinition(
        rule_code="ADCS_ATTITUDE_CLUSTER",
        suspected_subsystem="ADCS",
        title="Possible Attitude Determination & Control (ADCS) disturbance",
        hypothesis_template=(
            "Co-occurring roll, pitch, or yaw anomalies suggest a possible attitude disturbance, "
            "momentum wheel excursion, or pointing control perturbation."
        ),
        required_sensors=("roll", "pitch", "yaw"),
        min_alerts=2,
        requires_physical_alerts=True,
    ),
]

DEFAULT_CORRELATION_WINDOW_SECONDS = 120.0
