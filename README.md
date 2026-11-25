# SAT-TRIAGE — Satellite Telemetry Anomaly Triage Copilot

**AVISHKAR'26 — 24-Hour Hackathon Project**  
**Team:** DevCore (`AV26-BF34B6F9D2`)  
**Problem Statement:** 11 — Satellite Telemetry Anomaly Triage Copilot  
**Domain:** Full Stack Web Development

---

## Problem Statement

Satellite ground operations teams monitor thousands of telemetry channels across power, thermal, attitude, and communications subsystems. When anomalies occur during brief orbital passes, operators must rapidly separate sensor noise from real faults, assess subsystem impact, and coordinate triage actions under tight time constraints.

## Project Description

**SAT-TRIAGE** is a full-stack satellite telemetry anomaly triage copilot designed to provide operators with a real-time mission-control workspace backed by a resilient API and relational database layer.

- **Phase 1:** Versioned FastAPI backend, PostgreSQL via Docker Compose, structured JSON logging, centralized error handling, `User` ORM model with `bcrypt` hashing, and health diagnostics.
- **Phase 2:** Ground-station Mission Control UI (`Overview`, `Telemetry`, `Alerts`, `Incidents`, `System Diagnostics`) with responsive layout and explicit empty states.
- **Phase 3:** Backend NumPy synthetic telemetry generator (`SAT-01`), controllable fault-injection scenarios, `python-socketio` real-time streaming to Recharts dashboards, and bounded batch PostgreSQL persistence (`telemetry_readings`). All generated readings are explicitly marked as **SYNTHETIC SIMULATION DATA**.
- **Phase 4:** Statistical anomaly detection (rolling baseline + z-score, rate-of-change, engineering limits using NumPy, Pandas, SciPy), independent cross-signal sensor integrity verification (`MISSING`, `FROZEN`, `INVALID`, `STALE`), deduplicated persistent alerts in PostgreSQL (`alerts`), and live Socket.IO alert/integrity streaming.
- **Phase 5 (Current):** Configurable satellite subsystem dependency graph (`EPS`, `THERMAL`, `ADCS`, `OBC`, `SENSORS`), time-window alert correlation (`120s` default window), rule-based hybrid causal hypothesis engine with supporting/contradicting evidence and illustrative heuristic confidence, persistent `correlations` storage, and interactive `/fault-graph` operator view.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system diagram, detection algorithms, limitations, and alert lifecycle.

---

## Technology Stack

- **Frontend:** React 18, React Router 7, Socket.IO Client 4, Vite 5, JavaScript (ES Modules), Tailwind CSS 3, Recharts 2, Lucide React
- **Backend:** Python 3.14, FastAPI, Uvicorn, NumPy 2, Pandas 3, SciPy 1, python-socketio 5, SQLAlchemy 2, psycopg 3, Pydantic Settings, bcrypt
- **Database:** PostgreSQL 16 via Docker Compose
- **Testing:** pytest, FastAPI TestClient / httpx

---

## Detection Thresholds & Sensor Integrity Rules

Thresholds are centralized in [detection_config.py](backend/app/core/detection_config.py) and exposed read-only via `GET /api/v1/detection/config`:

- **Rolling Baseline & Z-Score:** `rolling_window_size = 30`, `min_baseline_samples = 8`, `z_score_warning = 3.5`, `z_score_critical = 5.0` (with per-sensor `min_meaningful_std` and `min_deviation_deadband` guards, plus independent `(satellite_id, sensor_name)` baselines excluding fault/anomalous excursions).
- **Deduplication & Recovery:** `dedup_cooldown_seconds = 10.0`, `recovery_consecutive_samples = 5` (auto-resolves open alerts after 5 consecutive clean nominal readings while preserving history).
- **Sensor Integrity (`WARNING` severity):**
  - `MISSING`: null `sensor_value`
  - `FROZEN`: `6` consecutive identical finite readings
  - `INVALID`: `NaN`/`Inf`, missing/naive timestamp, or outside `physical_valid_range`
  - `STALE`: > `6.0s` without updates while `simulator_running=True` (reports `STREAM_INACTIVE` when stopped)

| Sensor | Unit | Engineering Warning | Engineering Critical | Physical Valid Range | Max Rate (`/s`) | Deadband |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `battery_voltage` | `V` | `[24.0, 29.6]` | `[21.5, 30.8]` | `[0.0, 60.0]` | `0.35` | `0.6` |
| `temperature` | `°C` | `[5.0, 40.0]` | `[-5.0, 55.0]` | `[-150.0, 200.0]` | `1.8` | `2.2` |
| `roll` | `degrees` | `[-10.0, 10.0]` | `[-22.0, 22.0]` | `[-180.0, 180.0]` | `8.0` | `2.5` |
| `pitch` | `degrees` | `[-10.0, 10.0]` | `[-22.0, 22.0]` | `[-180.0, 180.0]` | `8.0` | `2.5` |
| `yaw` | `degrees` | `[-14.0, 14.0]` | `[-28.0, 28.0]` | `[-180.0, 180.0]` | `10.0` | `4.0` |

### Alert Lifecycle & Deduplication
- Persisted in PostgreSQL `alerts` table (`id`, `alert_id`, `satellite_id`, `sensor_name`, `alert_type`, `severity`, `status`, `title`, `description`, `observed_value`, `expected_range`, `z_score`, `reason_code`, `evidence` JSON, `first_detected_at`, `last_detected_at`, `occurrence_count`, `acknowledged_at`, `resolved_at`, `created_at`, `updated_at`).
- Continuing findings matching an `ACTIVE` or `ACKNOWLEDGED` `(satellite_id, sensor_name, alert_type)` update the existing row and increment `occurrence_count`.
- Operator transitions: `ACTIVE` → `ACKNOWLEDGED` (`POST /api/v1/alerts/{alert_id}/acknowledge`) → `RESOLVED` (`POST /api/v1/alerts/{alert_id}/resolve`).

### Hybrid Causal Fault Graph & Alert Correlation (Phase 5)
- Subsystem dependency topology configured in [fault_graph_config.py](backend/app/core/fault_graph_config.py) covering `EPS`, `THERMAL`, `ADCS`, `OBC`, and `SENSORS`, sensor-to-subsystem mappings, failure modes, and directed subsystem couplings (`PROVIDES_POWER`, `THERMAL_COUPLING`, `ATTITUDE_SOLAR_COUPLING`, `ATTITUDE_THERMAL_COUPLING`, `TELEMETRY_BUS`, `CONTROL_LOOP`).
- Deterministic rule-based correlation (`DEFAULT_CORRELATION_WINDOW_SECONDS = 120.0`, no LLM inference) groups temporally proximate Phase 4 alerts under explicit rules (`EPS_THERMAL_COUPLED_FAULT`, `ADCS_EPS_SOLAR_COUPLING`, `OBC_MULTI_CHANNEL_INTEGRITY`, `EPS_UNDERVOLTAGE_CLUSTER`, `THERMAL_EXCURSION_CLUSTER`, `ADCS_ATTITUDE_CLUSTER`).
- Persisted in PostgreSQL `correlations` table (`id`, `correlation_id`, `satellite_id`, `rule_code`, `suspected_subsystem`, `hypothesis`, `grouping_reason`, `related_alert_ids` JSON, `supporting_evidence` JSON, `contradicting_evidence` JSON, `confidence_score`, `confidence_explanation`, `status`, `window_start`, `window_end`, `acknowledged_at`, `dismissed_at`, `created_at`, `updated_at`).
- All hypotheses explicitly frame **possible common causes** with supporting/contradicting evidence and an illustrative heuristic confidence score — correlation never proves causation, and operators retain final authority (`ACTIVE` → `ACKNOWLEDGED` or `DISMISSED`).

---

## REST API Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Backend service status, version, environment, and uptime. |
| `GET` | `/health/db` | Executes `SELECT 1` against PostgreSQL (`200` connected, `503` unreachable). |
| `GET` | `/api/v1/info` | SAT-TRIAGE metadata, API version (`v1`), and Team DevCore details. |
| `POST` | `/api/v1/simulator/start` | Starts synthetic telemetry generation (`409` if already running). |
| `POST` | `/api/v1/simulator/stop` | Stops generation gracefully and flushes pending batch to PostgreSQL. |
| `GET` | `/api/v1/simulator/status` | Returns running state, sampling interval, active faults, and pipeline counters. |
| `POST` | `/api/v1/simulator/faults` | Activates a validated fault scenario (`fault_type`, optional `target_sensor`). |
| `POST` | `/api/v1/simulator/faults/clear` | Clears all active fault scenarios. |
| `GET` | `/api/v1/telemetry/latest` | Returns latest readings per sensor (live buffer or PostgreSQL fallback). |
| `GET` | `/api/v1/telemetry/history` | Returns paginated historical telemetry with `sensor_name` and time-range filters. |
| `GET` | `/api/v1/alerts` | Lists persisted alerts newest-first with filters (`satellite_id`, `sensor_name`, `severity`, `alert_type`, `status`) and pagination. |
| `GET` | `/api/v1/alerts/{alert_id}` | Returns full alert details and JSON `evidence`. |
| `POST` | `/api/v1/alerts/{alert_id}/acknowledge` | Transitions an active alert to `ACKNOWLEDGED`. |
| `POST` | `/api/v1/alerts/{alert_id}/resolve` | Transitions an alert to `RESOLVED`. |
| `GET` | `/api/v1/detection/status` | Returns detection engine status, processed sample count, open alert count, and 5-channel integrity snapshots. |
| `GET` | `/api/v1/detection/config` | Returns read-only statistical thresholds and sensor limits. |
| `GET` | `/api/v1/fault-graph` | Returns subsystem dependency nodes, sensors, persisted alert nodes, edges, and correlations. |
| `GET` | `/api/v1/fault-graph/correlations` | Lists persisted correlation hypotheses with status, subsystem, window, and pagination filters. |
| `GET` | `/api/v1/fault-graph/correlations/{correlation_id}` | Returns full correlation details, linked alerts, supporting/contradicting evidence, and confidence explanation. |
| `POST` | `/api/v1/fault-graph/correlations/{correlation_id}/acknowledge` | Transitions a correlation hypothesis to `ACKNOWLEDGED` and emits Socket.IO updates. |
| `POST` | `/api/v1/fault-graph/correlations/{correlation_id}/dismiss` | Transitions a correlation hypothesis to `DISMISSED` and emits Socket.IO updates. |

---

## Socket.IO Event Contract (`/socket.io`)

- `telemetry:update`: Live synthetic telemetry frame and pipeline counters.
- `simulation:status`: Simulator lifecycle status (`running`, `interval_seconds`, `active_faults`).
- `simulation:fault`: Fault activation and clearing notifications.
- `alert:new`: Newly persisted anomaly or integrity alert (`AlertRead` JSON).
- `alert:updated`: Updated/deduplicated, acknowledged, or resolved alert (`AlertRead` JSON).
- `detection:status`: Updated engine status and 5-channel `sensor_states` integrity snapshot.
- `integrity:issue`: Real-time sensor integrity finding (`MISSING`, `FROZEN`, `INVALID`, `STALE`).
- `fault_graph:update`: Live subsystem fault graph topology and correlation snapshot (`FaultGraphResponse` JSON).
- `correlation:new`: Newly persisted correlation hypothesis (`CorrelationRead` JSON).
- `correlation:updated`: Updated, acknowledged, or dismissed correlation hypothesis (`CorrelationRead` JSON).

---

## Reproducing Detection Scenarios

1. Start PostgreSQL (`docker compose up -d`), FastAPI (`uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`), and Vite (`npm run dev`).
2. Open `http://localhost:5173`, click **Start Simulation**, and observe ~10s of baseline frames (0 false alerts).
3. Inject **Battery Drop** or **Temp Spike** to observe `STATISTICAL_ANOMALY`, `RATE_OF_CHANGE`, and `ENGINEERING_LIMIT` alerts appear in **Overview** and **Alerts**.
4. Select a target sensor and inject **Frozen Sensor** (~6s) or **Missing Data** to observe integrity findings in **System Diagnostics** and **Alerts**.
5. Click **Acknowledge** / **Resolve** on alerts and refresh the page to confirm PostgreSQL persistence.
6. Inject **Battery Drop** and **Temp Spike** together, open **Fault Graph** (`/fault-graph`), inspect correlated subsystems (`EPS`, `THERMAL`), review supporting/contradicting evidence and illustrative confidence, switch time windows (`60s` / `120s` / `300s`), and verify **Acknowledge** / **Dismiss** persistence across page reload.

---

## Testing Instructions

```bash
cd backend
.\.venv\Scripts\pytest.exe -v tests
```

```bash
cd frontend
npm run build
```

---

## External Libraries and Licences

### Backend (Python)
| Package | Version | Licence |
| :--- | :--- | :--- |
| `fastapi` | 0.165.0 | MIT |
| `uvicorn` | 0.54.0 | BSD-3-Clause |
| `numpy` | 2.5.5 | BSD-3-Clause / MIT / 0BSD / Zlib / CC0-1.0 |
| `pandas` | 3.1.1 | BSD-3-Clause |
| `scipy` | 1.18.1 | BSD-3-Clause |
| `python-socketio` | 5.18.1 | MIT |
| `sqlalchemy` | 2.1.9 | MIT |
| `psycopg` | 3.3.9 | LGPL-3.0-only |
| `pydantic` | 2.14.4 | MIT |
| `pydantic-settings` | 2.16.3 | MIT |
| `email-validator` | 2.4.0 | Unlicense |
| `bcrypt` | 4.3.0 | Apache-2.0 |
| `pytest` | 8.4.2 | MIT |
| `httpx` | 0.28.1 | BSD-3-Clause |

### Frontend (JavaScript)
| Package | Version | Licence |
| :--- | :--- | :--- |
| `react` | 18.3.1 | MIT |
| `react-dom` | 18.3.1 | MIT |
| `react-router-dom` | 7.18.7 | MIT |
| `socket.io-client` | 4.8.4 | MIT |
| `recharts` | 2.15.4 | MIT |
| `lucide-react` | 0.460.0 | ISC |
| `vite` | 5.4.21 | MIT |
| `tailwindcss` | 3.4.19 | MIT |
| `postcss` | 8.5.33 | MIT |
| `autoprefixer` | 10.7.0 | MIT |
