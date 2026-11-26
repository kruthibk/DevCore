# Battery and Power Subsystem Troubleshooting Runbook

**Runbook ID:** BAT-RB-001  
**Version:** 1.0  
**Subsystem:** Battery and Electrical Power  
**Application:** Satellite Telemetry Anomaly Triage Copilot  
**Data Type:** Synthetic telemetry for prototype demonstration

## 1. Purpose

This runbook provides troubleshooting guidance for identifying and investigating abnormal battery and power telemetry readings.

It helps ground operators understand possible battery-related anomalies, validate sensor readings, investigate related telemetry parameters, and identify when further investigation is required.

This document is intended for an educational prototype using synthetic satellite telemetry. It is not an approved spacecraft operating procedure.

## 2. Subsystem Overview

The electrical power subsystem supplies electrical energy to spacecraft components.

A typical spacecraft power subsystem may include:
- Solar arrays for generating electrical power.
- Batteries for storing electrical energy.
- Power management and distribution equipment.
- Sensors for monitoring voltage, current, and temperature.

The battery stores energy and supplies power when required by the spacecraft.

Monitoring battery telemetry helps identify unusual electrical behaviour and possible power subsystem issues.

### 2.1 Important Telemetry Parameters

| Parameter | Description | Unit |
| :--- | :--- | :--- |
| Battery Voltage | Electrical potential across the battery | Volts (V) |
| Battery Current | Current flowing into or out of the battery | Amperes (A) |
| Battery Temperature | Temperature measured by the battery sensor | °C |
| State of Charge (SOC) | Estimated remaining battery capacity | % |
| Power Bus Voltage | Voltage of the spacecraft power distribution bus | Volts (V) |

Not every spacecraft provides all these measurements. The prototype should use only the parameters configured in its telemetry simulator.

### 2.2 Suggested Application Telemetry Field Mapping

The following are proposed application field names, not guaranteed simulator fields. Confirm each name against the telemetry simulator and retain only supported fields.

| Application Field Name | Parameter | Unit |
| :--- | :--- | :--- |
| `battery_voltage` | Battery Voltage | Volts (V) |
| `battery_current` | Battery Current | Amperes (A) |
| `battery_temperature` | Battery Temperature | Degrees Celsius (°C) |
| `battery_soc` | State of Charge | Percentage (%) |
| `power_bus_voltage` | Power Bus Voltage | Volts (V) |

## 3. Anomaly Identification

### 3.1 BAT-001: Sudden Battery Voltage Drop

**Description:**
Battery voltage decreases significantly compared with its recent readings.

**Possible indicators:**
- Sudden voltage decrease.
- Repeated voltage fluctuations.
- Voltage outside the configured operating range.
- Simultaneous changes in battery current.

**Possible causes:**
- Increased electrical load.
- Battery degradation.
- Power distribution issue.
- Abnormal charging or discharging behaviour.
- Battery voltage sensor malfunction.
- Telemetry transmission or measurement error.

**Investigation priority:** Based on the configured demonstration severity and available evidence.

### 3.2 BAT-002: Abnormal Battery Temperature

**Description:**
Battery temperature increases or decreases unexpectedly.

**Possible indicators:**
- Rapid temperature increase.
- Temperature outside configured limits.
- Unexpected differences between related temperature sensors.

**Possible causes:**
- Abnormal battery operating conditions.
- Thermal management issue.
- Sensor malfunction.
- Telemetry quality problem.

### 3.3 BAT-003: Unexpected Battery Current

**Description:**
Battery charging or discharging current behaves differently from its expected pattern.

**Possible indicators:**
- Unexpected current spikes.
- Unusual current fluctuations.
- Current behaviour inconsistent with voltage trends.

**Possible causes:**
- Changing electrical load.
- Charging system issue.
- Power distribution anomaly.
- Current sensor malfunction.
- Telemetry error.

### 3.4 BAT-004: Unexpected State of Charge Change

**Description:**
The reported battery state of charge changes unexpectedly.

**Possible indicators:**
- Sudden SOC decrease.
- SOC values outside the valid percentage range.
- SOC behaviour inconsistent with current measurements.

**Possible causes:**
- Increased energy consumption.
- Battery capacity estimation error.
- Battery degradation.
- SOC sensor or estimation issue.
- Telemetry processing error.

## 4. Telemetry Data Validation

Before diagnosing a battery anomaly, validate the quality of the available measurements.

### 4.1 Missing Data Check

Check whether battery voltage, current, temperature, or SOC readings are missing.

**Investigation:**
- Identify null or missing values.
- Check timestamps for data gaps.
- Verify whether the telemetry stream has stopped updating.

**Expected result:** Missing readings should be marked as unavailable, not replaced with zero.

### 4.2 Frozen Sensor Check

Check whether a sensor repeatedly reports exactly the same value.

**Investigation:**
- Compare consecutive readings.
- Calculate how long the value has remained unchanged.
- Compare the behaviour with other available measurements.

**Expected result:** Suspiciously constant values should be flagged for sensor verification.

### 4.3 Valid Range Check

Check whether the readings fall within configured engineering limits.

**Examples:**
- Battery SOC below 0% or above 100% is invalid.
- Voltage outside the configured sensor or subsystem range requires investigation.
- Physically impossible or malformed measurements should be flagged.

Do not use invented universal spacecraft voltage or temperature thresholds.

### 4.4 Cross-Signal Consistency Check

Compare related battery measurements.

**Examples:**
- Compare battery voltage with battery current.
- Compare battery temperature with voltage and current changes.
- Compare battery SOC trends with charging and discharging behaviour.
- Compare battery voltage with power bus voltage when available.

**Expected result:** Inconsistent measurements should be marked as suspicious and investigated.

**Important:** An integrity failure does not prove that the anomaly is false. A genuine hardware problem can also produce inconsistent telemetry.

## 5. Investigation Procedures

### 5.1 Procedure for Sudden Voltage Drop

1. Identify the timestamp of the voltage drop.
2. Examine battery voltage readings before and after the event.
3. Compare battery current during the same interval.
4. Examine battery temperature.
5. Review SOC readings if available.
6. Compare power bus voltage if available.
7. Check missing-data, frozen-sensor, and valid-range flags.
8. Review other alerts occurring around the same time.
9. Retrieve relevant historical battery incidents.
10. Identify possible causes supported by the evidence.

### 5.2 Procedure for Abnormal Battery Temperature

1. Identify when the temperature change began.
2. Examine the temperature trend.
3. Compare other battery or nearby temperature measurements.
4. Review battery voltage and current.
5. Check sensor integrity.
6. Examine simultaneous thermal or power alerts.
7. Identify whether the behaviour is persistent or temporary.

### 5.3 Procedure for Unexpected Current Behaviour

1. Identify whether current represents charging or discharging.
2. Examine current readings over time.
3. Compare current with battery voltage.
4. Examine SOC changes if available.
5. Check for missing or frozen readings.
6. Compare related power measurements.
7. Review other incidents during the same interval.

### 5.4 Procedure for Unexpected State of Charge Change

1. Identify when the SOC change began.
2. Examine SOC readings before and after the event.
3. Compare the SOC trend with battery current and its charging or discharging direction, if known.
4. Review battery voltage and battery temperature.
5. Check whether SOC is within the valid percentage range of 0% to 100%.
6. Check for missing, frozen, delayed, or malformed telemetry.
7. Review other power subsystem alerts during the same interval.
8. Record possible explanations supported by the available evidence; do not treat an SOC inconsistency alone as proof of battery failure.

## 6. Recommended Investigation Guidance

Based on the retrieved evidence, the application may recommend that the operator:
- Review battery voltage and current trends.
- Compare related power measurements.
- Verify battery temperature readings.
- Check whether telemetry is complete and reliable.
- Examine other subsystem alerts.
- Review historical incidents for similar patterns.
- Consult approved mission-specific battery documentation when available.

Recommendations must remain investigative.

The application must not generate or execute battery charging, discharging, switching, resetting, or other spacecraft control commands.

## 7. Escalation Conditions

Flag the incident for operator attention when:
- Battery voltage remains outside configured limits.
- Abnormal voltage behaviour continues across multiple readings.
- Battery temperature shows a persistent abnormal trend.
- Multiple power measurements indicate a possible subsystem problem.
- SOC measurements behave inconsistently with other available telemetry.
- Sensor integrity problems prevent reliable assessment.
- Multiple related subsystem anomalies occur together.

Mission-specific escalation thresholds must come from approved mission documentation.

### 7.1 Prototype Triage Severity Guidance

The following qualitative labels may be used by the prototype to describe investigation urgency. They are not spacecraft mission severity levels and must not replace approved mission rules.
- **Low:** An isolated or short-lived unusual reading with no corroborating signal and no persistent data-quality issue. Continue monitoring the available synthetic telemetry.
- **Medium:** An anomaly persists across multiple readings, repeats, or is supported by another related measurement. Recommend further operator investigation.
- **High:** Multiple related power measurements show persistent abnormal behaviour, or telemetry quality prevents a reliable assessment of a potentially significant event. Flag for prompt operator attention.

The prototype must explain which observed indicators led to a suggested label. If evidence is insufficient, report severity as Undetermined rather than guessing. Configured detector thresholds and mission-specific escalation criteria remain authoritative.

## 8. Cross-Subsystem Relationships

Battery anomalies may occur alongside other subsystem anomalies.

**Subsystem ownership for battery temperature:** This runbook covers battery temperature only when investigating battery and electrical-power behaviour (for example, a battery temperature change occurring with voltage or current changes). The Temperature/Thermal runbook owns broader thermal behaviour across spacecraft components and thermal-control equipment. If an incident involves both battery electrical behaviour and wider thermal behaviour, retrieve both runbooks and keep their findings distinct.

### 8.1 Battery and Thermal Relationship

**Example:**
- Battery voltage decreases.
- Battery temperature increases.
- Battery current changes.

**Possible interpretation:** The measurements may indicate an abnormal battery operating condition.

Further evidence is required before identifying a root cause.

### 8.2 Battery and Attitude Relationship

**Example:**
- Battery voltage decreases.
- Attitude measurements show unexpected changes.

**Possible interpretation:** The system should examine whether both events occurred during the same time interval and whether other power measurements support a relationship.

Correlation does not prove causation.

## 9. RAG Retrieval Metadata

The following metadata should be associated with relevant document chunks during indexing.

### 9.1 Detector Event-to-Runbook Mapping

The detector identifies an event; this mapping directs the application to the relevant runbook section for explanation and investigation guidance. The event labels below are illustrative and must be aligned with the actual detector output names used by the application.

| Detector Event | Runbook Section |
| :--- | :--- |
| Sudden battery voltage drop | BAT-001 |
| Abnormal battery temperature in a battery/power context | BAT-002 |
| Unexpected battery current | BAT-003 |
| Unexpected state of charge change | BAT-004 |

### 9.2 Chunk-Level Metadata

Attach metadata to each indexed text chunk so retrieval can filter and cite the relevant source. Suggested fields:

| Metadata Field | Example Value |
| :--- | :--- |
| `runbook_id` | `BAT-RB-001` |
| `subsystem` | `battery_power` |
| `section` | `BAT-001 or the relevant section heading` |
| `anomaly_id` | `BAT-001` (use null for general guidance) |
| `document_type` | `troubleshooting_runbook` |
| `version` | `1.0` |
| `source_file` | `battery_runbook.md` |

Store the exact source section or page/line reference with each chunk where practical, so the copilot can identify the evidence used in its response. These are suggested indexing fields; implement only fields supported by the ingestion pipeline.

| Field | Value |
| :--- | :--- |
| Runbook ID | BAT-RB-001 |
| Subsystem | Battery / Power |
| Keywords | battery, voltage, current, SOC, power, temperature |
| Anomaly IDs | BAT-001, BAT-002, BAT-003, BAT-004 |
| Document Type | Troubleshooting Runbook |
| Version | 1.0 |

**Suggested retrieval queries:**
- Why did battery voltage suddenly decrease?
- What could cause abnormal battery temperature?
- How should unexpected battery current be investigated?
- How can battery telemetry integrity be checked?
- What should be checked when battery voltage and current disagree?

## 10. References

The following NASA resources provide technical background. They are not approved mission-specific troubleshooting procedures.
1. NASA Small Spacecraft Systems Virtual Institute — Power Subsystems  
   https://www.nasa.gov/smallsat-institute/sst-soa/power-subsystems/
2. NASA Small Spacecraft Systems Virtual Institute — State of the Art of Small Spacecraft Technology  
   https://www.nasa.gov/smallsat-institute/
3. NASA Technical Reports Server  
   https://ntrs.nasa.gov/

## 11. Limitations and Safety Notes

- This runbook is designed for a synthetic telemetry demonstration.
- No universal battery voltage or temperature thresholds are specified.
- Mission-specific limits must be obtained from approved engineering documentation.
- Possible causes must not be presented as confirmed failures.
- Sensor integrity checks cannot conclusively determine whether an anomaly is genuine.
- LLM recommendations must be grounded in retrieved runbook evidence.
- No autonomous spacecraft control or command execution is permitted.
