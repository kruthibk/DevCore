# SAT-TRIAGE Architecture (Phases 1–4)

## Overview

SAT-TRIAGE is a full-stack web platform for satellite telemetry anomaly triage, built for **AVISHKAR'26** (Problem Statement 11) by **Team DevCore (`AV26-BF34B6F9D2`)**.

- **Phase 1:** Project foundation, FastAPI service, PostgreSQL via Docker Compose, `User` ORM model, health probes.
- **Phase 2:** Ground-station Mission Control UI shell with Overview, Telemetry, Alerts, Incidents, and System Diagnostics pages.
- **Phase 3:** Backend-driven NumPy synthetic telemetry simulator (`SAT-01`), fault-injection scenarios, Socket.IO real-time streaming, and bounded batch PostgreSQL persistence.
- **Phase 4 (Current):** Statistical anomaly detection (NumPy, Pandas, SciPy), cross-signal sensor integrity verification, deduplicated persistent alerts, and live Socket.IO alert streaming.

## Component Flow

```text
+-------------------------------------------------------+
|          React + Vite Mission Control UI              |
|  - Live Alerts Queue + Evidence & Ack/Resolve         |
|  - Sensor Integrity Panel (System Diagnostics)        |
|  - Live Recharts Telemetry + Simulator Controls       |
+---------------------------+---------------------------+
                            | HTTP REST + Socket.IO (/socket.io)
                            v
+-------------------------------------------------------+
|      FastAPI + python-socketio (ASGI Sub-App)         |
|  - Simulator Loop -> TelemetryGenerator (NumPy)       |
|  - DetectionPipelineService (asyncio.Lock):           |
|      1. SensorIntegrityService (MISSING/FROZEN/...)   |
|      2. StatisticalAnomalyDetector (Pandas/SciPy)     |
|      3. AlertService (Deduplicate & Persist)          |
|      4. Socket.IO Broadcast (alert:*, detection:*)    |
+---------------------------+---------------------------+
                            | Scoped Sessions (asyncio.to_thread)
                            v
+-------------------------------------------------------+
|              PostgreSQL 16 (Docker)                   |
|  - users                                              |
|  - telemetry_readings                                 |
|  - alerts (dedup index + JSON evidence)               |
+-------------------------------------------------------+
```

## Detection Algorithms & Limitations

1. **Rolling Baseline & Z-Score (`STATISTICAL_ANOMALY`):**
   - Uses a per-sensor bounded rolling window (`rolling_window_size = 30`) evaluated with `pandas.Series` mean and sample standard deviation (`ddof=1`).
   - Requires `min_baseline_samples = 8` before evaluating z-scores, guards against zero/near-zero standard deviation (`min_meaningful_std`), and applies a per-sensor `min_deviation_deadband` to prevent false alerts on slow orbital sinusoidal cycles.
   - Records an `illustrative_two_tailed_p` via `scipy.stats.norm.sf` in `evidence` as supporting context only (not a calibrated fault probability or causal claim).
   - *Limitations:* Univariate per-channel analysis; assumes local stationarity across the trailing 30-sample window; statistical deviations indicate unusual numerical behavior, not confirmed spacecraft failure.

2. **Rate-of-Change (`RATE_OF_CHANGE`):**
   - Computes `|Δvalue / Δt|` across consecutive valid samples and flags excursions above sensor-specific `max_rate_per_sec` limits.

3. **Engineering Limits (`ENGINEERING_LIMIT`):**
   - Evaluates incoming values against centralized `engineering_warning` and `engineering_critical` operational bounds, explicitly distinct from statistical z-score deviations.

4. **Cross-Signal Sensor Integrity (`SENSOR_MISSING`, `SENSOR_FROZEN`, `SENSOR_INVALID`, `SENSOR_STALE`):**
   - Inspects raw values and timezone-aware timestamps independently of simulator `quality_status` labels.
   - `MISSING`: null readings (excluded from statistical baselines).
   - `FROZEN`: `6` consecutive identical values within `1e-9` tolerance.
   - `INVALID`: `NaN`/`Inf`, missing/naive timestamps, or values outside `physical_valid_range`.
   - `STALE`: evaluated only when `simulator_running=True` and elapsed time exceeds `6.0s`; when stopped, channels report `STREAM_INACTIVE`.

5. **Alert Deduplication & Lifecycle:**
   - Active/acknowledged duplicates keyed by `(satellite_id, sensor_name, alert_type)` update `last_detected_at`, `observed_value`, `evidence`, and increment `occurrence_count` instead of creating duplicate rows.
   - Lifecycle transitions: `ACTIVE` → `ACKNOWLEDGED` → `RESOLVED` (human operators remain responsible for all triage decisions).
