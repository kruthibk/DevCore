"""Automated tests for RBAC and Incident Log + Audit Trail workflows (JWT authenticated)."""

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.v1.endpoints.simulator import get_simulator_service  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.telemetry import FaultActionResponse  # noqa: E402


@pytest.fixture()
def rbac_client(tmp_path: Path) -> Generator[dict, None, None]:
    """Provide an isolated SQLite-backed TestClient with authenticated ADMIN, OPERATOR, and VIEWER users."""
    db_file = tmp_path / "incidents_rbac_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def _enable_sqlite_fks(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    test_pw = "TestRolePass!2026"
    with TestingSessionLocal() as seed_db:
        seed_db.add_all(
            [
                User(
                    username="inc_admin",
                    email="inc_admin@devcore.space",
                    password_hash=hash_password(test_pw),
                    role="ADMIN",
                    is_active=True,
                ),
                User(
                    username="inc_operator",
                    email="inc_operator@devcore.space",
                    password_hash=hash_password(test_pw),
                    role="OPERATOR",
                    is_active=True,
                ),
                User(
                    username="inc_viewer",
                    email="inc_viewer@devcore.space",
                    password_hash=hash_password(test_pw),
                    role="VIEWER",
                    is_active=True,
                ),
            ]
        )
        seed_db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fake_sim = type("FakeSim", (), {})()
    fake_sim.inject_fault = AsyncMock(
        return_value=FaultActionResponse(
            action="activated",
            fault_type="battery_drop",
            active_faults=[],
            timestamp=datetime.now(timezone.utc),
        )
    )
    fake_sim.clear_faults = AsyncMock(
        return_value=FaultActionResponse(
            action="cleared",
            active_faults=[],
            timestamp=datetime.now(timezone.utc),
        )
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_simulator_service] = lambda: fake_sim

    with TestClient(app) as client:
        yield {"client": client, "password": test_pw}

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def _login_headers(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_rbac_enforcement_viewer_operator_admin(rbac_client: dict) -> None:
    client: TestClient = rbac_client["client"]
    pw: str = rbac_client["password"]

    # Unauthenticated calls must fail with 401
    assert client.get("/api/v1/incidents").status_code == 401
    assert client.get("/api/v1/admin/users").status_code == 401

    viewer_headers = _login_headers(client, "inc_viewer", pw)
    op_headers = _login_headers(client, "inc_operator", pw)
    admin_headers = _login_headers(client, "inc_admin", pw)

    # VIEWER is blocked with 403 on operational/mutating endpoints
    assert (
        client.post(
            "/api/v1/incidents",
            headers=viewer_headers,
            json={"title": "Blocked", "summary": "Viewer cannot create"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/copilot/ask",
            headers=viewer_headers,
            json={"question": "Battery voltage drop"},
        ).status_code
        == 403
    )

    # OPERATOR cannot invoke ADMIN-only fault injection, reindex, or user admin
    assert (
        client.post(
            "/api/v1/simulator/faults",
            headers=op_headers,
            json={"fault_type": "battery_drop"},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/copilot/reindex", headers=op_headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=op_headers).status_code == 403

    # ADMIN has full access
    assert client.get("/api/v1/admin/users", headers=admin_headers).status_code == 200
    assert (
        client.post(
            "/api/v1/simulator/faults",
            headers=admin_headers,
            json={"fault_type": "battery_drop"},
        ).status_code
        == 200
    )


def test_incident_lifecycle_and_immutable_audit_trail(rbac_client: dict) -> None:
    client: TestClient = rbac_client["client"]
    pw: str = rbac_client["password"]
    op_headers = _login_headers(client, "inc_operator", pw)
    admin_headers = _login_headers(client, "inc_admin", pw)
    viewer_headers = _login_headers(client, "inc_viewer", pw)

    create_resp = client.post(
        "/api/v1/incidents",
        headers=op_headers,
        json={
            "title": "EPS undervoltage excursion on SAT-01",
            "summary": "Battery voltage dropped below 21.5 V during simulated fault.",
            "subsystem": "battery_power",
            "severity": "CRITICAL",
            "linked_alert_ids": ["ALT-BAT001"],
            "copilot_summary": "Investigate battery voltage trend per BAT-RB-001 section 5.1.",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    inc_id = created["incident_id"]
    assert inc_id.startswith("INC-")
    assert created["status"] == "OPEN"
    assert created["created_by"] == "inc_operator"
    assert len(created["logs"]) == 1
    assert created["logs"][0]["action"] == "CREATED"
    assert created["logs"][0]["to_status"] == "OPEN"

    patch_1 = client.patch(
        f"/api/v1/incidents/{inc_id}",
        headers=op_headers,
        json={"status": "INVESTIGATING", "note": "Reviewing bus telemetry."},
    )
    assert patch_1.status_code == 200
    assert patch_1.json()["status"] == "INVESTIGATING"

    note_resp = client.post(
        f"/api/v1/incidents/{inc_id}/logs",
        headers=admin_headers,
        json={"note": "Confirmed synthetic fault cleared; voltage recovering."},
    )
    assert note_resp.status_code == 201

    patch_2 = client.patch(
        f"/api/v1/incidents/{inc_id}",
        headers=admin_headers,
        json={"status": "CLOSED", "assigned_to": "inc_admin"},
    )
    assert patch_2.status_code == 200

    detail_resp = client.get(f"/api/v1/incidents/{inc_id}", headers=op_headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "CLOSED"
    assert detail["assigned_to"] == "inc_admin"

    logs = detail["logs"]
    assert [entry["action"] for entry in logs] == [
        "CREATED",
        "STATUS_CHANGE",
        "NOTE_ADDED",
        "STATUS_CHANGE",
    ]
    assert logs[1]["from_status"] == "OPEN"
    assert logs[1]["to_status"] == "INVESTIGATING"
    assert logs[1]["actor"] == "inc_operator"
    assert logs[2]["actor"] == "inc_admin"
    assert logs[3]["from_status"] == "INVESTIGATING"
    assert logs[3]["to_status"] == "CLOSED"

    # VIEWER blocked from appending notes
    assert (
        client.post(
            f"/api/v1/incidents/{inc_id}/logs",
            headers=viewer_headers,
            json={"note": "Unauthorized viewer note"},
        ).status_code
        == 403
    )

    list_resp = client.get("/api/v1/incidents", headers=op_headers)
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] == 1
    assert list_body["summary"]["closed"] == 1
    assert list_body["summary"]["resolved"] == 1
