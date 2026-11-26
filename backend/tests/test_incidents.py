"""Automated tests for RBAC, demo user seeding, and Incident Log + Audit Trail workflows."""

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
from app.db.base import Base  # noqa: E402
from app.db.init_db import seed_demo_users  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.telemetry import FaultActionResponse  # noqa: E402


@pytest.fixture()
def rbac_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Provide an isolated SQLite-backed TestClient with seeded RBAC demo users."""
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

    with TestingSessionLocal() as seed_db:
        first_seed = seed_demo_users(seed_db)
        second_seed = seed_demo_users(seed_db)
        assert first_seed == 3
        assert second_seed == 0

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
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def test_demo_user_seeding_login_and_users_endpoint(rbac_client: TestClient) -> None:
    users_resp = rbac_client.get("/api/v1/users")
    assert users_resp.status_code == 200
    users = users_resp.json()
    assert [u["username"] for u in users] == ["admin", "operator", "viewer"]
    assert all("password_hash" not in u for u in users)

    bad_login = rbac_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    login_resp = rbac_client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "AdminPass!2026"},
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["role"] == "ADMIN"

    me_resp = rbac_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["actor"]["role"] == "ADMIN"
    assert me_resp.json()["actor"]["auth_mode"] == "bearer"

    default_me = rbac_client.get("/api/v1/auth/me")
    assert default_me.status_code == 200
    assert default_me.json()["actor"]["role"] == "OPERATOR"
    assert default_me.json()["actor"]["auth_mode"] == "demo_default"


def test_rbac_enforcement_viewer_operator_admin(rbac_client: TestClient) -> None:
    # Login as VIEWER via real DB user
    viewer_login = rbac_client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "ViewerPass!2026"},
    )
    assert viewer_login.status_code == 200
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}

    # VIEWER can read
    assert rbac_client.get("/api/v1/incidents", headers=viewer_headers).status_code == 200
    assert rbac_client.get("/api/v1/users", headers=viewer_headers).status_code == 200

    # VIEWER is blocked with 403 on all mutating / copilot-ask endpoints
    assert (
        rbac_client.post(
            "/api/v1/incidents",
            headers=viewer_headers,
            json={"title": "Blocked", "summary": "Viewer cannot create"},
        ).status_code
        == 403
    )
    assert (
        rbac_client.post(
            "/api/v1/copilot/ask",
            headers=viewer_headers,
            json={"question": "Battery voltage drop"},
        ).status_code
        == 403
    )
    assert (
        rbac_client.post(
            "/api/v1/simulator/faults",
            headers=viewer_headers,
            json={"fault_type": "battery_drop"},
        ).status_code
        == 403
    )

    # OPERATOR (header or default) cannot invoke ADMIN-only fault injection or reindex
    op_headers = {"X-Operator-Role": "OPERATOR", "X-Operator-Name": "op-alice"}
    assert (
        rbac_client.post(
            "/api/v1/simulator/faults",
            headers=op_headers,
            json={"fault_type": "battery_drop"},
        ).status_code
        == 403
    )
    assert rbac_client.post("/api/v1/copilot/reindex", headers=op_headers).status_code == 403

    # ADMIN can inject/clear faults
    admin_headers = {"X-Operator-Role": "ADMIN", "X-Operator-Name": "admin-bob"}
    assert (
        rbac_client.post(
            "/api/v1/simulator/faults",
            headers=admin_headers,
            json={"fault_type": "battery_drop"},
        ).status_code
        == 200
    )


def test_incident_lifecycle_and_immutable_audit_trail(rbac_client: TestClient) -> None:
    op_headers = {"X-Operator-Role": "OPERATOR", "X-Operator-Name": "ops-lead"}
    admin_headers = {"X-Operator-Role": "ADMIN", "X-Operator-Name": "flight-director"}

    create_resp = rbac_client.post(
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
    assert created["created_by"] == "ops-lead"
    assert len(created["logs"]) == 1
    assert created["logs"][0]["action"] == "CREATED"
    assert created["logs"][0]["to_status"] == "OPEN"

    # Transition OPEN -> INVESTIGATING -> MITIGATED -> CLOSED
    patch_1 = rbac_client.patch(
        f"/api/v1/incidents/{inc_id}",
        headers=op_headers,
        json={"status": "INVESTIGATING", "note": "Reviewing bus telemetry."},
    )
    assert patch_1.status_code == 200
    assert patch_1.json()["status"] == "INVESTIGATING"

    # Append standalone investigation note
    note_resp = rbac_client.post(
        f"/api/v1/incidents/{inc_id}/logs",
        headers=admin_headers,
        json={"note": "Confirmed synthetic fault cleared; voltage recovering."},
    )
    assert note_resp.status_code == 201

    patch_2 = rbac_client.patch(
        f"/api/v1/incidents/{inc_id}",
        headers=admin_headers,
        json={"status": "CLOSED", "assigned_to": "flight-director"},
    )
    assert patch_2.status_code == 200

    # Verify full detail & chronological audit log timeline
    detail_resp = rbac_client.get(f"/api/v1/incidents/{inc_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "CLOSED"
    assert detail["assigned_to"] == "flight-director"

    logs = detail["logs"]
    assert [entry["action"] for entry in logs] == [
        "CREATED",
        "STATUS_CHANGE",
        "NOTE_ADDED",
        "STATUS_CHANGE",
    ]
    assert logs[1]["from_status"] == "OPEN"
    assert logs[1]["to_status"] == "INVESTIGATING"
    assert logs[1]["actor"] == "ops-lead"
    assert logs[2]["actor"] == "flight-director"
    assert logs[3]["from_status"] == "INVESTIGATING"
    assert logs[3]["to_status"] == "CLOSED"

    # VIEWER still blocked from mutating or logging notes
    assert (
        rbac_client.post(
            f"/api/v1/incidents/{inc_id}/logs",
            headers={"X-Operator-Role": "VIEWER"},
            json={"note": "Unauthorized viewer note"},
        ).status_code
        == 403
    )

    # Verify list summary counts
    list_resp = rbac_client.get("/api/v1/incidents")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] == 1
    assert list_body["summary"]["closed"] == 1
    assert list_body["summary"]["resolved"] == 1
