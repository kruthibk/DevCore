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

**Phase 1 (Current Milestone)** establishes the end-to-end project foundation:
- Versioned FastAPI backend with structured JSON logging, centralized error handling, CORS, and SQLAlchemy + PostgreSQL integration.
- Initial `User` ORM model with strict constraints and salted `bcrypt` password hashing (never storing plaintext passwords).
- Dark satellite mission-control React shell with live backend connectivity, database connectivity, application status, and Recharts probe latency visualization driven by real backend endpoints.
- Docker Compose PostgreSQL setup and automated backend test suite.

---

## Architecture

See [docs/architecture.md](docs/architecture.md) for the component diagram and graceful failure-handling flow.

1. **Frontend (`frontend/`)**: React 18 + Vite + Tailwind CSS + Recharts dark mission-control UI polling `GET /health`, `GET /health/db`, and `GET /api/v1/info`.
2. **Backend (`backend/`)**: FastAPI application with `Pydantic Settings` configuration, request-ID middleware, structured JSON logging, centralized exception handlers, and SQLAlchemy 2.x session management.
3. **Database (`docker-compose.yml`)**: PostgreSQL 16 (`postgres:16-alpine`) with a persistent Docker volume (`sat_triage_pgdata`) and `pg_isready` health check.

---

## Technology Stack

- **Frontend:** React 18, Vite 5, JavaScript (ES Modules), Tailwind CSS 3, Recharts 2, Lucide React
- **Backend:** Python 3.14, FastAPI, Uvicorn, SQLAlchemy 2, psycopg 3, Pydantic Settings, bcrypt
- **Database:** PostgreSQL 16 via Docker Compose
- **Testing:** pytest, FastAPI TestClient / httpx

---

## Folder Structure

```text
DevCore/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   └── info.py
│   │   │       └── router.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── exceptions.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── init_db.py
│   │   │   └── session.py
│   │   ├── models/
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── health.py
│   │   │   ├── info.py
│   │   │   └── user.py
│   │   ├── services/
│   │   │   └── health_service.py
│   │   └── main.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   ├── test_info.py
│   │   └── test_user_model.py
│   └── requirements.txt
├── docs/
│   └── architecture.md
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js
│   │   ├── components/
│   │   │   ├── DiagnosticsView.jsx
│   │   │   ├── Header.jsx
│   │   │   ├── LatencyChart.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   └── StatusCards.jsx
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   └── vite.config.js
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## Installation Instructions

### Prerequisites
- Python 3.11+ (tested on Python 3.14.0)
- Node.js 20+ and npm (tested on Node v24.11.0 / npm 11.6.1)
- Docker & Docker Compose

### 1. Environment Setup

Copy `.env.example` to `.env` at the repository root and update secrets as needed:

```bash
cp .env.example .env
```

Required environment variables:
- `DATABASE_URL`: SQLAlchemy PostgreSQL connection string (e.g., `postgresql+psycopg://sat_triage:sat_triage_dev@localhost:5433/sat_triage`)
- `JWT_SECRET_KEY`: Secret key for token signing (replace placeholder before production)
- `CORS_ORIGINS`: Comma-separated allowed frontend origins (e.g., `http://localhost:5173,http://127.0.0.1:5173`)
- `API_HOST`: Bind host for Uvicorn (default `0.0.0.0`)
- `API_PORT`: Bind port for Uvicorn (default `8000`)

### 2. Database Setup

Start PostgreSQL using Docker Compose:

```bash
docker compose up -d
docker compose ps
```

### 3. Backend Startup

Create a virtual environment, install dependencies, and start FastAPI:

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

### 4. Frontend Startup

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## API Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Returns backend service status, version, environment, and uptime. |
| `GET` | `/health/db` | Executes `SELECT 1` against PostgreSQL. Returns `200` when connected or `503` with structured error metadata when unreachable. |
| `GET` | `/api/v1/info` | Returns SAT-TRIAGE metadata, API version (`v1`), and Team DevCore details. |

---

## Testing Instructions

Run automated backend tests:

```bash
cd backend
pytest -v tests
```

Build the frontend production bundle:

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
| `recharts` | 2.15.4 | MIT |
| `lucide-react` | 0.460.0 | ISC |
| `vite` | 5.4.21 | MIT |
| `tailwindcss` | 3.4.19 | MIT |
| `postcss` | 8.5.33 | MIT |
| `autoprefixer` | 10.7.0 | MIT |
