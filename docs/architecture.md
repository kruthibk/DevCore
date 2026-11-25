# SAT-TRIAGE Architecture (Phases 1–3)

## Overview

SAT-TRIAGE is a full-stack web platform for satellite telemetry anomaly triage, built for **AVISHKAR'26** (Problem Statement 11) by **Team DevCore (`AV26-BF34B6F9D2`)**.

- **Phase 1:** Project foundation, FastAPI service, PostgreSQL via Docker Compose, `User` ORM model, health probes.
- **Phase 2:** Ground-station Mission Control UI shell with Overview, Telemetry, Alerts, Incidents, and System Diagnostics pages.
- **Phase 3 (Current):** Backend-driven NumPy synthetic telemetry simulator (`SAT-01`), fault-injection scenarios, Socket.IO real-time streaming, and bounded batch PostgreSQL persistence.

## Component Flow

```text
+-------------------------------------------------------+
|          React + Vite Mission Control UI              |
|  - Socket.IO client (/socket.io) -> 60-pt live buffer |
|  - Recharts live telemetry & diagnostics charts       |
|  - Simulator & Fault Injection Controls               |
+---------------------------+---------------------------+
                            | HTTP REST + WebSocket / Polling
                            v
+-------------------------------------------------------+
|      FastAPI + python-socketio (ASGI Sub-App)         |
|  - GET /health, /health/db, /api/v1/info              |
|  - POST /api/v1/simulator/{start,stop,faults,...}     |
|  - GET /api/v1/telemetry/{latest,history}             |
|  - TelemetrySimulatorService (asyncio loop + lock)    |
|  - TelemetryGenerator (NumPy)                         |
+---------------------------+---------------------------+
                            | Controlled Batch Flush (asyncio.to_thread)
                            v
+-------------------------------------------------------+
|              PostgreSQL 16 (Docker)                   |
|  - users                                              |
|  - telemetry_readings (indexed on ts & sat/sensor/ts) |
+-------------------------------------------------------+
```

## Telemetry Pipeline & Resilience

1. **Generation:** `TelemetryGenerator` uses NumPy (`numpy.random.default_rng`) to synthesize `battery_voltage`, `temperature`, `roll`, `pitch`, and `yaw` readings tagged with `SYNTHETIC SIMULATION DATA` and timezone-aware UTC timestamps.
2. **Real-Time Streaming:** `TelemetrySimulatorService` emits `telemetry:update` over `python-socketio` on every sampling tick without blocking the ASGI event loop.
3. **Bounded Batch Persistence:** Generated samples accumulate in a bounded `deque(maxlen=500)` and flush to PostgreSQL in controlled batches (`SIMULATOR_PERSIST_BATCH_SIZE`, default `10`) via `asyncio.to_thread`. Database outages are logged and tracked via `failed_persist_batches` / `last_persistence_error` without crashing the simulator or falsely incrementing `persisted_count`.
4. **Graceful Health Probes:** `GET /health` remains `200 OK` during database outages, while `GET /health/db` returns `503 Service Unavailable` with structured error metadata.
