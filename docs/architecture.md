# SAT-TRIAGE Architecture (Phase 1)

## Overview

SAT-TRIAGE is a full-stack web platform for satellite telemetry anomaly triage, built for **AVISHKAR'26** (Problem Statement 11) by **Team DevCore (`AV26-BF34B6F9D2`)**.

Phase 1 establishes the production-ready project foundation:

1. **Mission-Control Frontend (`frontend/`)**: A dark-themed React + Vite + Tailwind CSS + Recharts shell that polls live backend and database health endpoints without hardcoded connectivity states.
2. **REST API Backend (`backend/`)**: A versioned FastAPI service featuring Pydantic Settings configuration, structured JSON logging, centralized error handling, CORS, SQLAlchemy ORM modeling, and graceful PostgreSQL failure handling.
3. **PostgreSQL Persistence (`docker-compose.yml`)**: A containerized PostgreSQL 16 instance with persistent volume storage and health checks.

## Component Flow

```text
+-----------------------------------+
|   React + Vite Mission Control    |
|  Tailwind CSS  |  Recharts        |
|  Polls /health, /health/db,       |
|  and /api/v1/info                 |
+-----------------+-----------------+
                  | HTTP / CORS
                  v
+-----------------------------------+
|      FastAPI Backend (Uvicorn)    |
|  - Request ID & JSON Logging      |
|  - Centralized Exception Handler  |
|  - GET /health                    |
|  - GET /health/db                 |
|  - GET /api/v1/info               |
+-----------------+-----------------+
                  | SQLAlchemy 2 + psycopg 3
                  v
+-----------------------------------+
|       PostgreSQL 16 (Docker)      |
|  - Table: users                   |
|  - Health probe: SELECT 1         |
+-----------------------------------+
```

## Graceful Database Failure Handling

- During FastAPI startup (`lifespan`), `init_db()` attempts `Base.metadata.create_all()` inside a guarded block so the API service still boots and serves `GET /health` even if PostgreSQL is temporarily unavailable.
- `GET /health/db` runs a lightweight `SELECT 1` probe and returns HTTP `200 OK` when connected or HTTP `503 Service Unavailable` with a structured JSON payload (`status: "unhealthy"`, `database: "disconnected"`) when PostgreSQL is unreachable.
