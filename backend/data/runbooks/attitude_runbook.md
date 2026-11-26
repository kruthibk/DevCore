# Attitude and Orientation Subsystem Troubleshooting Runbook

**Runbook ID:** ATT-RB-001  
**Version:** 1.0  
**Subsystem:** Attitude Determination and Control System (ADCS)  
**Application:** Satellite Telemetry Anomaly Triage Copilot  
**Data Type:** Synthetic telemetry for prototype demonstration

## 1. Purpose

This runbook provides troubleshooting guidance for identifying and investigating abnormal spacecraft attitude and orientation telemetry.

It helps operators understand possible attitude anomalies, validate sensor readings, investigate related measurements, and identify when further investigation is required.

This document is intended for an educational prototype using synthetic satellite telemetry. It is not an approved spacecraft operating procedure.

## 2. Subsystem Overview

The Attitude Determination and Control System (ADCS) determines and controls the orientation of a spacecraft.

Attitude describes the spacecraft's orientation relative to a reference frame.

The ADCS may use sensors and actuators to determine and control spacecraft orientation.

Examples of attitude sensors and equipment include:
- Star trackers.
- Sun sensors.
- Gyroscopes.
- Magnetometers.
- Reaction wheels.

The exact equipment depends on the spacecraft design.

Monitoring attitude telemetry helps identify unexpected orientation changes, unusual rotation, and possible sensor inconsistencies.

### 2.1 Important Telemetry Parameters

| Parameter | Description | Unit |
| :--- | :--- | :--- |
| Roll | Rotation around the spacecraft's roll axis | Degrees |
| Pitch | Rotation around the spacecraft's pitch axis | Degrees |
| Yaw | Rotation around the spacecraft's yaw axis | Degrees |
| Angular Velocity | Rate of spacecraft rotation | Degrees/second or radians/second |
| Attitude Error | Difference between desired and estimated attitude | Degrees or radians |
| Reaction Wheel Speed | Rotational speed of a reaction wheel, if available | RPM |

The prototype should use only the attitude parameters configured in its telemetry simulator.

Angle conventions and reference frames must be consistent throughout the application.

### 2.2 Suggested Application Telemetry Field Mapping

The following are proposed application field names, not guaranteed simulator fields. Confirm each name against the telemetry simulator and retain only supported fields. The angular-velocity and attitude-error units must match the simulator configuration.

| Application Field Name | Parameter | Unit |
| :--- | :--- | :--- |
| `roll` | Roll | Degrees (°) |
| `pitch` | Pitch | Degrees (°) |
| `yaw` | Yaw | Degrees (°) |
| `angular_velocity` | Angular Velocity | Degrees/second (°/s) or radians/second (rad/s), as configured |
| `attitude_error` | Attitude Error | Degrees (°) or radians, as configured |
| `reaction_wheel_speed` | Reaction Wheel Speed | RPM, if available |

Do not convert or compare angular measurements until their units, angle conventions, and reference frames are known.

### 2.3 Subsystem Ownership

This runbook owns attitude and orientation anomalies, including roll, pitch, yaw, angular velocity, attitude error, and available reaction-wheel measurements. The Battery/Power runbook owns battery voltage, current, state of charge, and battery-temperature behaviour in an electrical-power context. The Temperature/Thermal runbook owns broader temperature behaviour across spacecraft components and thermal-control equipment.

When an incident spans multiple subsystems, the copilot may retrieve more than one runbook. It must keep each subsystem's evidence distinct and must not infer causation from simultaneous alerts alone.

## 3. Anomaly Identification

### 3.1 ATT-001: Unexpected Attitude Deviation

**Description:**

The spacecraft orientation deviates unexpectedly from its expected attitude.

**Possible indicators:**
- Sudden change in roll, pitch, or yaw.
- Increasing attitude error.
- Persistent deviation from expected orientation.
- Unexpected changes across multiple attitude parameters.

**Possible causes:**
- Attitude sensor error.
- Unexpected external disturbance.
- Attitude control system issue.
- Actuator-related issue.
- Incorrect or inconsistent telemetry.

### 3.2 ATT-002: Unusual Angular Velocity

**Description:**

The measured spacecraft rotation rate changes unexpectedly.

**Possible indicators:**
- Sudden angular velocity increase.
- Unexpected rotation fluctuations.
- Angular velocity outside configured limits.
- Rotation behaviour inconsistent with attitude measurements.

**Possible causes:**
- Unexpected spacecraft rotation.
- Attitude control disturbance.
- Sensor malfunction.
- Actuator-related issue.
- Telemetry measurement error.

### 3.3 ATT-003: Attitude Sensor Inconsistency

**Description:**

Different attitude measurements or sensor estimates disagree.

**Possible indicators:**
- Conflicting attitude estimates.
- One sensor reporting an unexpected change.
- Frozen or invalid sensor values.
- Sudden jumps in orientation readings.

**Possible causes:**
- Sensor malfunction.
- Sensor measurement interference.
- Incorrect sensor data.
- Telemetry timing or processing issue.
- Different reference frames or measurement conventions.

### 3.4 ATT-004: Persistent Attitude Error

**Description:**

The difference between desired and estimated spacecraft attitude remains unusually high.

**Possible indicators:**
- Attitude error remaining outside configured limits.
- Repeated attitude error increases.
- Attitude error not returning towards its expected range.

**Possible causes:**
- Attitude control performance issue.
- External disturbance.
- Incorrect attitude estimation.
- Sensor or actuator-related problem.
- Telemetry processing error.

## 4. Telemetry Data Validation

Before diagnosing an attitude anomaly, validate the quality of the available measurements.

### 4.1 Missing Data Check

Check whether roll, pitch, yaw, angular velocity, or attitude error readings are missing.

**Investigation:**
- Identify null or missing values.
- Check timestamps for data gaps.
- Verify whether the telemetry stream has stopped updating.

**Expected result:** Missing readings should be marked as unavailable, not replaced with zero.

### 4.2 Frozen Sensor Check

Check whether an attitude sensor repeatedly reports the same value.

**Investigation:**
- Compare consecutive readings.
- Calculate how long the value has remained unchanged.
- Compare with angular velocity and other available measurements.

**Expected result:** Suspiciously constant values should be flagged for sensor verification.

### 4.3 Valid Range Check

Check whether attitude measurements fall within configured sensor and application limits.

**Examples:**
- Malformed or non-numeric measurements should be flagged.
- Angular velocity outside configured limits requires investigation.
- Invalid attitude error values should be identified.

**Important:** Angle values require special handling. For example, a transition from +179° to -179° may represent a small angular change rather than a sudden 358° rotation.

The application must use an appropriate angle-wrapping method when calculating angular differences.

### 4.4 Cross-Signal Consistency Check

Compare related attitude measurements.

**Examples:**
- Compare roll, pitch, and yaw changes.
- Compare attitude changes with angular velocity.
- Compare attitude estimates from different sensors, if available.
- Examine reaction wheel speed if available.

**Expected result:** Suspicious inconsistencies should be marked for further investigation.

A disagreement does not automatically prove that a sensor is faulty.

## 5. Investigation Procedures

### 5.1 Procedure for Unexpected Attitude Deviation

1. Identify the timestamp when the deviation began.
2. Examine roll, pitch, and yaw readings.
3. Compare measurements before and after the event.
4. Examine angular velocity.
5. Review attitude error if available.
6. Compare readings from available attitude sensors.
7. Check for missing, frozen, or invalid sensor values.
8. Examine simultaneous battery and temperature anomalies.
9. Review historical attitude incidents.
10. Identify possible explanations supported by the available evidence.

### 5.2 Procedure for Unusual Angular Velocity

1. Identify when the angular velocity changed.
2. Examine the angular velocity trend.
3. Compare angular velocity with attitude changes.
4. Review available reaction wheel measurements.
5. Check the quality of sensor readings.
6. Identify whether the behaviour is temporary or persistent.
7. Review other simultaneous subsystem alerts.

### 5.3 Procedure for Attitude Sensor Inconsistency

1. Identify which measurements disagree.
2. Compare their timestamps.
3. Check whether measurements use the same reference frame.
4. Verify angle units and conventions.
5. Examine consecutive readings from each sensor.
6. Check for missing or frozen values.
7. Compare angular velocity measurements.
8. Identify whether the disagreement can be explained by normal measurement differences.
9. Flag unresolved inconsistencies for operator investigation.

### 5.4 Procedure for Persistent Attitude Error

1. Identify when the attitude error began increasing.
2. Examine the error trend.
3. Compare estimated and desired attitude.
4. Review angular velocity.
5. Examine available sensor and actuator telemetry.
6. Check sensor integrity flags.
7. Identify related subsystem alerts.
8. Review historical attitude incidents.

## 6. Recommended Investigation Guidance

Based on retrieved evidence, the application may recommend that the operator:
- Review attitude and angular velocity trends.
- Compare available attitude sensor measurements.
- Verify timestamps, units, and reference frames.
- Check sensor integrity and telemetry completeness.
- Examine reaction wheel measurements if available.
- Review related subsystem anomalies.
- Consult approved mission-specific ADCS documentation.

Recommendations must remain investigative.

The application must not generate or execute attitude correction, thruster firing, reaction wheel switching, sensor switching, or other spacecraft control commands.

## 7. Escalation Conditions

Flag the incident for operator attention when:
- Attitude deviation exceeds configured mission limits.
- Unexpected rotation continues over multiple readings.
- Attitude error remains unusually high.
- Multiple attitude measurements indicate abnormal behaviour.
- Sensor disagreement prevents reliable attitude estimation.
- Attitude anomalies occur alongside other subsystem anomalies.
- Telemetry quality problems prevent reliable assessment.

Mission-specific escalation thresholds must come from approved mission documentation.

### 7.1 Prototype Triage Severity Guidance

The prototype may attach a qualitative triage label to explain investigation urgency. These labels are not spacecraft mission severity classifications and must not replace approved mission rules or configured detector thresholds.

| Prototype label | Guidance |
| :--- | :--- |
| Low | A brief or isolated attitude deviation with no corroborating abnormal measurements and no identified data-quality concern. |
| Medium | An attitude deviation or angular-velocity change persists across multiple readings, repeats, or is supported by another related measurement. |
| High | Multiple related attitude measurements show persistent abnormal behaviour, attitude error remains unusually high, or the event is accompanied by other subsystem anomalies. |
| Undetermined | Available telemetry is missing, invalid, inconsistent, or insufficient to assess the event reliably. |

The prototype must explain which observed indicators support its suggested label. Use Undetermined when evidence is insufficient rather than guessing. The operator retains responsibility for assessing urgency.

## 8. Cross-Subsystem Relationships

### 8.1 Attitude and Battery Relationship

**Example:**
- Battery voltage decreases.
- Attitude measurements show unexpected changes.
- Angular velocity also changes.

**Possible interpretation:** The system should investigate whether these events occurred during the same time interval and whether additional power measurements support a relationship.

Correlation does not prove that the power anomaly caused the attitude anomaly.

### 8.2 Attitude and Temperature Relationship

**Example:**
- Electronics temperature increases.
- Attitude deviation is detected.

**Possible interpretation:** Both events may be related to a common operating condition or may be independent events.

Additional evidence is required.

## 9. RAG Retrieval Metadata

The following metadata should be associated with relevant document chunks during indexing.

### 9.1 Detector Event-to-Runbook Mapping

The detector flags an unusual telemetry event; this mapping directs the application to the relevant runbook section for investigation context. The event labels below are suggested examples and must be aligned with the actual event names emitted by the detector.

| Suggested detector event | Runbook section |
| :--- | :--- |
| Unexpected attitude deviation | ATT-001 |
| Unusual angular velocity | ATT-002 |
| Attitude sensor inconsistency | ATT-003 |
| Persistent attitude error | ATT-004 |

The detector event does not establish a confirmed hardware failure. The LLM should explain the alert using retrieved evidence and preserve uncertainty.

### 9.2 Chunk-Level Metadata

Attach metadata to each indexed text chunk so retrieval can filter results and identify the source. Use the actual section and anomaly identifier for each chunk.

| Metadata Field | Example Value |
| :--- | :--- |
| `runbook_id` | `ATT-RB-001` |
| `subsystem` | `attitude_adcs` |
| `section` | `3.1 Unexpected Attitude Deviation` |
| `anomaly_id` | `ATT-001` (use null for general guidance) |
| `document_type` | `troubleshooting_runbook` |
| `version` | `1.0` |
| `source_file` | `attitude_runbook.md` |

Store the source section or chunk identifier with retrieved text so the copilot can cite the runbook ID and section in its response. Metadata values must describe the chunk actually being indexed; do not assign every anomaly ID to every chunk. Implement only fields supported by the ingestion pipeline.

| Field | Value |
| :--- | :--- |
| Runbook ID | ATT-RB-001 |
| Subsystem | Attitude / Orientation |
| Keywords | attitude, orientation, ADCS, roll, pitch, yaw, angular velocity, reaction wheel |
| Anomaly IDs | ATT-001, ATT-002, ATT-003, ATT-004 |
| Document Type | Troubleshooting Runbook |
| Version | 1.0 |

**Suggested retrieval queries:**
- Why did spacecraft orientation suddenly change?
- What could cause unexpected angular velocity?
- How should attitude sensor disagreement be investigated?
- What does persistent attitude error indicate?
- How can frozen attitude sensors be identified?
- Why should angle wrapping be considered when comparing orientation readings?

## 10. References

The following NASA resources provide technical background. They are not approved mission-specific troubleshooting procedures.
1. NASA Small Spacecraft Systems Virtual Institute — Guidance, Navigation and Control  
   https://www.nasa.gov/smallsat-institute/sst-soa/guidance-navigation-and-control/
2. NASA Small Spacecraft Systems Virtual Institute  
   https://www.nasa.gov/smallsat-institute/
3. NASA Technical Reports Server  
   https://ntrs.nasa.gov/

## 11. Limitations and Safety Notes

- This runbook is designed for a synthetic telemetry demonstration.
- No universal attitude or angular velocity thresholds are specified.
- Mission-specific limits must be obtained from approved engineering documentation.
- Angle representation and reference frames must be handled consistently.
- Possible causes must not be presented as confirmed failures.
- Sensor integrity checks cannot conclusively determine whether an anomaly is genuine.
- LLM recommendations must be grounded in retrieved runbook evidence.
- No autonomous spacecraft control or command execution is permitted.
