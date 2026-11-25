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
- **Phase 3 (Current):** Backend NumPy synthetic telemetry generator (`SAT-01`), controllable fault-injection scenarios, `python-socketio` real-time streaming to Recharts dashboards, and bounded batch PostgreSQL persistence (`telemetry_readings`). All generated readings are explicitly marked as **SYNTHETIC SIMULATION DATA**.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full system diagram and telemetry resilience flow.

---

## Technology Stack

- **Frontend:** React 18, React Router 7, Socket.IO Client 4, Vite 5, JavaScript (ES Modules), Tailwind CSS 3, Recharts 2, Lucide React
- **Backend:** Python 3.14, FastAPI, Uvicorn, NumPy 2, python-socketio 5, SQLAlchemy 2, psycopg 3, Pydantic Settings, bcrypt
- **Database:** PostgreSQL 16 via Docker Compose
- **Testing:** pytest, FastAPI TestClient / httpx

---

## Sensor Definitions (SAT-01 Synthetic Prototype)

| Sensor Name | Unit | Nominal Behavior |
| :--- | :--- | :--- |
| `battery_voltage` | `V` | Sinusoidal orbital cycle around `28.0 V` with Gaussian noise |
| `temperature` | `°C` | Thermal cycle around `22.5 °C` with Gaussian noise |
| `roll` | `degrees` | Smooth ADCS variation within normal operating bounds |
| `pitch` | `degrees` | Smooth ADCS variation within normal operating bounds |
| `yaw` | `degrees` | Smooth ADCS variation within normal operating bounds |

### Synthetic Fault Injection Scenarios

| Fault Type | Effect on Synthetic Telemetry |
| :--- | :--- |
| `battery_drop` | Gradually decreases `battery_voltage` (`quality_status: FAULT_SIMULATED`) |
| `temperature_spike` | Ramps `temperature` above nominal operating range (`quality_status: FAULT_SIMULATED`) |
| `attitude_disturbance` | Injects large excursions across `roll`, `pitch`, and `yaw` (`quality_status: FAULT_SIMULATED`) |
| `frozen_sensor` | Freezes a selected `target_sensor` at its last value (`quality_status: FROZEN`) |
| `missing_data` | Emits `null` readings for a selected `target_sensor` (`quality_status: MISSING`) |

---

## PostgreSQL Schema

### `users`
- `id` (PK), `username` (unique), `email` (unique), `password_hash`, `role` (`operator` | `analyst` | `admin`), `created_at` (`timestamptz`)

### `telemetry_readings`
- `id` (PK)
- `satellite_id` (`varchar(32)`, indexed)
- `sensor_name` (`varchar(64)`, indexed, check constraint for 5 supported sensors)
- `sensor_value` (`numeric(12,4)`, nullable for `MISSING` samples)
- `unit` (`varchar(32)`)
- `timestamp` (`timestamptz`, indexed via `ix_telemetry_timestamp`)
- `quality_status` (`varchar(32)`, check constraint: `NOMINAL` | `FAULT_SIMULATED` | `FROZEN` | `MISSING`)
- Composite lookup index: `ix_telemetry_sat_sensor_ts (satellite_id, sensor_name, timestamp)`

---

## REST API Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Backend service status, version, environment, and uptime. |
| `GET` | `/health/db` | Executes `SELECT 1` against PostgreSQL (`200` connected, `503` unreachable). |
| `GET` | `/api/v1/info` | SAT-TRIAGE metadata, API version (`v1`), and Team DevCore details. |
| `POST` | `/api/v1/simulator/start` | Starts synthetic telemetry generation (rejects duplicate starts with `409`). |
| `POST` | `/api/v1/simulator/stop` | Stops generation gracefully and flushes pending batch to PostgreSQL. |
| `GET` | `/api/v1/simulator/status` | Returns running state, sampling interval, active faults, and pipeline counters. |
| `POST` | `/api/v1/simulator/faults` | Activates a validated fault scenario (`fault_type`, optional `target_sensor`). |
| `POST` | `/api/v1/simulator/faults/clear` | Clears all active fault scenarios. |
| `GET` | `/api/v1/telemetry/latest` | Returns latest readings per sensor (live buffer or PostgreSQL fallback). |
| `GET` | `/api/v1/telemetry/history` | Returns paginated historical telemetry with `sensor_name` and time-range filters. |

---

## Socket.IO Event Contract (`/socket.io`)

### `telemetry:update`
```json
{
  "satellite_id": "SAT-01",
  "data_origin": "SYNTHETIC SIMULATION DATA",
  "simulator_running": true,
  "timestamp": "2026-11-25T12:30:00+00:00",
  "active_faults": [],
  "generated_count": 25,
  "streamed_count": 25,
  "persisted_count": 20,
  "last_persistence_error": null,
  "readings": [
    {
      "satellite_id": "SAT-01",
      "sensor_name": "battery_voltage",
      "sensor_value": 28.042,
      "unit": "V",
      "timestamp": "2026-11-25T12:30:00+00:00",
      "quality_status": "NOMINAL"
    }
  ]
}
```

### `simulation:status`
Broadcasts simulator start/stop/initial connection status (`running`, `interval_seconds`, `active_faults`, `generated_count`, `streamed_count`, `persisted_count`).

### `simulation:fault`
```json
{
  "action": "activated",
  "data_origin": "SYNTHETIC SIMULATION DATA",
  "fault_type": "temperature_spike",
  "target_sensor": null,
  "active_faults": [
    { "fault_type": "temperature_spike", "target_sensor": null, "activated_at": "2026-11-25T12:31:00+00:00" }
  ],
  "timestamp": "2026-11-25T12:31:00+00:00"
}
```

---

## Installation & Startup

### 1. Environment Setup
```bash
cp .env.example .env
```

### 2. Database Setup
```bash
docker compose up -d
docker compose ps
```

### 3. Backend Startup
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend Startup
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## Testing Instructions

```bash
cd backend
pytest -v tests
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
