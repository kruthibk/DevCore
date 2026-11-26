"""Phase 8 security, JWT authentication, RBAC, Verification Wall, and Human Approval tests."""

from collections.abc import Generator
from pathlib import Path
import sys
import time

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture()
def phase8_client(tmp_path: Path) -> Generator[dict, None, None]:
    """Isolated SQLite TestClient with one seeded ADMIN and clean registration state."""
    db_file = tmp_path / "phase8_security.db"
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

    admin_pw = "Phase8Admin!2026"
    with TestingSessionLocal() as db:
        db.add(
            User(
                username="chief_admin",
                email="chief_admin@devcore.space",
                password_hash=hash_password(admin_pw),
                role="ADMIN",
                is_active=True,
            )
        )
        db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield {"client": client, "session_factory": TestingSessionLocal, "admin_pw": admin_pw}

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def _valid_bat_payload(overrides: dict | None = None) -> dict:
    chunk = {
        "chunk_id": "BAT-RB-001::5-1-Procedure-for-Sudden-Voltage-Drop::0::f507bba2",
        "runbook_id": "BAT-RB-001",
        "document_name": "battery_runbook.md",
        "section_heading": "5.1 Procedure for Sudden Voltage Drop",
        "subsystem": "battery_power",
        "similarity_score": 0.86,
        "text": "Review battery_voltage trend against configured warning bound 24.0 V and critical bound 21.5 V.",
    }
    base = {
        "source_type": "COPILOT",
        "satellite_id": "SAT-01",
        "subsystem": "battery_power",
        "question": "What should an operator investigate when battery voltage suddenly drops?",
        "anomaly_summary": "Observed battery_voltage drop below 24.0 V; investigative checks retrieved from BAT-RB-001.",
        "verified_observations": ["Verified battery_voltage = 20.8 V (below 21.5 V critical limit)."],
        "possible_explanations": ["Possible power bus load shift or sensor integrity issue (not confirmed)."],
        "supporting_evidence": ["BAT-RB-001 section 5.1 covers sudden voltage drops."],
        "contradicting_or_missing_evidence": [],
        "recommended_checks": [
            "Inspect battery_voltage trend before and after the excursion.",
            "Check sensor integrity status for telemetry dropouts before assuming hardware fault.",
        ],
        "uncertainty_and_limitations": ["Correlation does not prove causation; human approval required."],
        "citations": [
            {
                "chunk_id": chunk["chunk_id"],
                "runbook_id": chunk["runbook_id"],
                "document_name": chunk["document_name"],
                "section_heading": chunk["section_heading"],
                "subsystem": chunk["subsystem"],
                "similarity_score": 0.86,
            }
        ],
        "retrieved_evidence": [chunk],
        "verified_context": {
            "satellite_id": "SAT-01",
            "supported_channels": ["battery_voltage", "temperature", "roll", "pitch", "yaw"],
            "latest_readings": {"battery_voltage": {"sensor_value": 20.8, "unit": "V"}},
        },
        "generation_status": "GENERATED",
    }
    if overrides:
        base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Authentication & Authorization Tests
# ---------------------------------------------------------------------------


def test_auth_registration_login_logout_jwt_and_inactive_account(phase8_client: dict) -> None:
    client: TestClient = phase8_client["client"]
    session_factory = phase8_client["session_factory"]

    # Protected endpoint without auth -> 401
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/verification/recommendations").status_code == 401
    assert (
        client.post("/api/v1/decisions/REC-DOESNTEXIST/approve", json={}).status_code == 401
    )

    # Registration always assigns OPERATOR even if extra role field is passed
    reg_pw = "OperatorPass!2026"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ops_alice",
            "email": "alice@devcore.space",
            "password": reg_pw,
            "role": "ADMIN",
        },
    )
    assert reg.status_code == 201
    reg_body = reg.json()
    assert reg_body["user"]["role"] == "OPERATOR"
    assert "password_hash" not in reg_body["user"]
    op_token = reg_body["access_token"]

    # Duplicate email registration rejected (409)
    dup = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ops_alice_2",
            "email": "alice@devcore.space",
            "password": reg_pw,
        },
    )
    assert dup.status_code == 409

    # Incorrect password rejected (401)
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"username": "ops_alice", "password": "WrongPassword999"},
    )
    assert bad_login.status_code == 401

    # Successful login
    ok_login = client.post(
        "/api/v1/auth/login",
        json={"username": "ops_alice", "password": reg_pw},
    )
    assert ok_login.status_code == 200
    login_token = ok_login.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login_token}"}).status_code == 200

    # Invalid JWT rejected (401)
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.jwt.token"}).status_code
        == 401
    )

    # Expired JWT rejected (401)
    settings = get_settings()
    expired_token = create_access_token(
        subject="ops_alice",
        role="OPERATOR",
        secret_key=settings.jwt_secret_key,
        user_id=reg_body["user"]["id"],
        expires_seconds=-10,
        algorithm=settings.jwt_algorithm,
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}).status_code
        == 401
    )

    # Logout revokes token -> subsequent use returns 401
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {op_token}"})
    assert logout_res.status_code == 200
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {op_token}"}).status_code
        == 401
    )

    # Inactive account rejected on login and protected endpoints (403)
    with session_factory() as db:
        u = db.query(User).filter(User.username == "ops_alice").one()
        u.is_active = False
        db.commit()

    assert (
        client.post("/api/v1/auth/login", json={"username": "ops_alice", "password": reg_pw}).status_code
        == 403
    )
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login_token}"}).status_code
        == 403
    )


def test_rbac_authorization_and_admin_controls(phase8_client: dict) -> None:
    client: TestClient = phase8_client["client"]
    admin_pw: str = phase8_client["admin_pw"]

    op_reg = client.post(
        "/api/v1/auth/register",
        json={"username": "op_user", "email": "op_user@devcore.space", "password": "OperatorPass!2026"},
    ).json()
    op_headers = {"Authorization": f"Bearer {op_reg['access_token']}"}
    op_id = op_reg["user"]["id"]

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"username": "chief_admin", "password": admin_pw},
    ).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
    admin_id = admin_login["user"]["id"]

    # Operator can access operator endpoints
    assert client.get("/api/v1/verification/recommendations", headers=op_headers).status_code == 200
    assert client.get("/api/v1/decisions/history", headers=op_headers).status_code == 200

    # Operator attempting admin operations -> 403
    assert client.get("/api/v1/admin/users", headers=op_headers).status_code == 403
    assert (
        client.patch(
            f"/api/v1/admin/users/{op_id}/role",
            headers=op_headers,
            json={"role": "ADMIN"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/admin/users/{op_id}/status",
            headers=op_headers,
            json={"is_active": False},
        ).status_code
        == 403
    )

    # Admin accessing admin endpoints -> 200
    admin_users = client.get("/api/v1/admin/users", headers=admin_headers)
    assert admin_users.status_code == 200
    assert admin_users.json()["audit_summary"]["total_users"] == 2

    # Admin cannot modify own role or deactivate self -> 403
    assert (
        client.patch(
            f"/api/v1/admin/users/{admin_id}/role",
            headers=admin_headers,
            json={"role": "OPERATOR"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/admin/users/{admin_id}/status",
            headers=admin_headers,
            json={"is_active": False},
        ).status_code
        == 403
    )

    # Admin can promote operator and toggle active status
    role_upd = client.patch(
        f"/api/v1/admin/users/{op_id}/role",
        headers=admin_headers,
        json={"role": "ADMIN"},
    )
    assert role_upd.status_code == 200
    assert role_upd.json()["role"] == "ADMIN"

    status_upd = client.patch(
        f"/api/v1/admin/users/{op_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert status_upd.status_code == 200
    assert status_upd.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Deterministic Verification Wall Tests
# ---------------------------------------------------------------------------


def test_verification_wall_rules_and_deterministic_outcomes(phase8_client: dict) -> None:
    client: TestClient = phase8_client["client"]
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "ver_op", "email": "ver_op@devcore.space", "password": "OperatorPass!2026"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    # 1. Valid citations & grounded checks -> VERIFIED (even deterministically repeated)
    res_ok_1 = client.post("/api/v1/verification/evaluate", headers=headers, json=_valid_bat_payload())
    assert res_ok_1.status_code == 201
    b1 = res_ok_1.json()
    assert b1["latest_verification_status"] == "VERIFIED"
    assert len(b1["latest_verification"]["checks"]) == 10
    assert all(c["status"] == "PASS" for c in b1["latest_verification"]["checks"])

    res_ok_2 = client.post("/api/v1/verification/evaluate", headers=headers, json=_valid_bat_payload())
    assert res_ok_2.json()["latest_verification_status"] == b1["latest_verification_status"]

    # 2. Invalid/fabricated citations -> REJECTED
    bad_cit = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {
                "citations": [
                    {
                        "chunk_id": "FAKE-999::invented",
                        "runbook_id": "FAKE-999",
                        "document_name": "fake.md",
                        "section_heading": "Invented",
                    }
                ]
            }
        ),
    )
    assert bad_cit.status_code == 201
    assert bad_cit.json()["latest_verification_status"] == "REJECTED"

    # 3. Unsupported telemetry channels -> REJECTED
    bad_chan = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {"verified_observations": ["Observed battery_current = 18.4 A and battery_soc = 32%."]}
        ),
    )
    assert bad_chan.json()["latest_verification_status"] == "REJECTED"

    # 4. Autonomous spacecraft command instructions -> REJECTED
    bad_cmd = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {"recommended_checks": ["Fire thruster and switch battery bus automatically."]}
        ),
    )
    assert bad_cmd.json()["latest_verification_status"] == "REJECTED"

    # 5. Unsupported engineering thresholds -> REJECTED
    bad_thresh = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {"anomaly_summary": "Battery voltage fell below the universal threshold of 19.25 V."}
        ),
    )
    assert bad_thresh.json()["latest_verification_status"] == "REJECTED"

    # 6. Unsupported root-cause claims -> REJECTED
    bad_cause = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {"possible_explanations": ["Confirmed root cause: proven hardware failure in cell 3."]}
        ),
    )
    assert bad_cause.json()["latest_verification_status"] == "REJECTED"

    # 7. Missing evidence -> NEEDS_REVIEW (and AI self-claim 'VERIFIED' ignored!)
    missing_ev = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {
                "retrieved_evidence": [],
                "citations": [],
                "ai_claimed_status": "VERIFIED",
                "generation_status": "INSUFFICIENT_EVIDENCE",
            }
        ),
    )
    assert missing_ev.json()["latest_verification_status"] == "NEEDS_REVIEW"

    # 8. Contradictory evidence -> NEEDS_REVIEW
    contra_ev = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {
                "contradicting_or_missing_evidence": [
                    "Sensor integrity warning: battery_voltage stream exhibits contradictory frozen readings."
                ]
            }
        ),
    )
    assert contra_ev.json()["latest_verification_status"] == "NEEDS_REVIEW"


# ---------------------------------------------------------------------------
# Human Operator Approval Workflow Tests
# ---------------------------------------------------------------------------


def test_human_approval_rejection_investigation_and_history_preservation(phase8_client: dict) -> None:
    client: TestClient = phase8_client["client"]
    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "decision_op", "email": "dec_op@devcore.space", "password": "OperatorPass!2026"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    # Create a VERIFIED recommendation
    ver_resp = client.post("/api/v1/verification/evaluate", headers=headers, json=_valid_bat_payload()).json()
    rec_id = ver_resp["recommendation_id"]
    ver_id = ver_resp["latest_verification"]["verification_id"]

    # Unauthenticated approval blocked (401)
    assert client.post(f"/api/v1/decisions/{rec_id}/approve", json={}).status_code == 401

    # Request further investigation first (preserves history)
    inv_resp = client.post(
        f"/api/v1/decisions/{rec_id}/request-investigation",
        headers=headers,
        json={"reason": "Verify prior orbital pass voltage curve before sign-off."},
    )
    assert inv_resp.status_code == 201
    assert inv_resp.json()["latest_decision_status"] == "INVESTIGATION_REQUESTED"

    # Approve VERIFIED recommendation -> 201, command_executed strictly False
    app_resp = client.post(
        f"/api/v1/decisions/{rec_id}/approve",
        headers=headers,
        json={"notes": "Approved investigative checklist only; no spacecraft commands."},
    )
    assert app_resp.status_code == 201
    app_body = app_resp.json()
    assert app_body["latest_decision_status"] == "APPROVED"
    assert app_body["latest_verification_status"] == "VERIFIED"
    assert app_body["latest_decision"]["command_executed"] is False

    # Re-evaluate recommendation and ensure historical decisions & verifications are preserved
    re_eval = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload({"recommendation_id": rec_id}),
    )
    assert re_eval.status_code == 201
    re_body = re_eval.json()
    assert len(re_body["verifications"]) == 2
    assert len(re_body["decisions"]) == 2
    assert re_body["verifications"][0]["verification_id"] == ver_id

    # Create a REJECTED recommendation and verify approval is blocked (409)
    rej_eval = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {"recommended_checks": ["Fire thruster immediately."]}
        ),
    ).json()
    rej_rec_id = rej_eval["recommendation_id"]
    assert rej_eval["latest_verification_status"] == "REJECTED"

    blocked_approve = client.post(
        f"/api/v1/decisions/{rej_rec_id}/approve",
        headers=headers,
        json={},
    )
    assert blocked_approve.status_code == 409

    # Rejecting requires non-empty reason (422 if missing/short)
    missing_reason = client.post(
        f"/api/v1/decisions/{rej_rec_id}/reject",
        headers=headers,
        json={"reason": "no"},
    )
    assert missing_reason.status_code == 422

    # Valid rejection recorded; original verification status remains REJECTED
    valid_reject = client.post(
        f"/api/v1/decisions/{rej_rec_id}/reject",
        headers=headers,
        json={"reason": "Rejected per autonomous thruster command safety violation."},
    )
    assert valid_reject.status_code == 201
    assert valid_reject.json()["latest_decision_status"] == "REJECTED"
    assert valid_reject.json()["latest_verification_status"] == "REJECTED"

    # Decision history endpoint lists all 3 decisions chronologically
    hist = client.get("/api/v1/decisions/history", headers=headers)
    assert hist.status_code == 200
    assert hist.json()["total"] == 3
    assert all(item["command_executed"] is False for item in hist.json()["items"])
    assert all(item["linked_incident_id"] for item in hist.json()["items"])

    # Rejected source_type PREDICIVE_SIM is removed from schema
    pred_rejected = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload({"source_type": "PREDICTIVE_SIM"}),
    )
    assert pred_rejected.status_code == 422


def test_unified_decision_incident_timeline_and_no_duplicates(phase8_client: dict) -> None:
    client: TestClient = phase8_client["client"]
    session_factory = phase8_client["session_factory"]

    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "unified_op", "email": "unified@devcore.space", "password": "OperatorPass!2026"},
    ).json()
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    # 1. Seed a real Alert and matching Correlation + verify Copilot auto-attaches Correlation
    from datetime import datetime, timezone
    from app.models.alert import Alert
    from app.models.correlation import Correlation
    from app.schemas.copilot import CopilotAskRequest
    from app.services.copilot_service import gather_verified_context

    now = datetime.now(timezone.utc)
    with session_factory() as db:
        db.add(
            Alert(
                alert_id="ALT-UNIFIED1",
                satellite_id="SAT-01",
                sensor_name="battery_voltage",
                alert_type="ENGINEERING_LIMIT",
                severity="CRITICAL",
                status="ACTIVE",
                title="Critical battery undervoltage",
                description="Battery bus fell below 21.5 V.",
                observed_value=20.4,
                expected_range="[21.5, 30.8] V",
                z_score=-6.2,
                reason_code="ENGINEERING_CRITICAL_LIMIT",
                evidence={"unit": "V"},
                first_detected_at=now,
                last_detected_at=now,
                occurrence_count=1,
            )
        )
        db.add(
            Correlation(
                correlation_id="CORR-UNIFIED1",
                satellite_id="SAT-01",
                rule_code="EPS_UNDERVOLTAGE_CLUSTER",
                suspected_subsystem="EPS",
                hypothesis="Multiple EPS alerts indicate possible power bus drop.",
                grouping_reason="Grouped EPS alerts.",
                related_alert_ids=["ALT-UNIFIED1"],
                supporting_evidence=[{"kind": "ALERT_OBSERVATION", "summary": "Voltage 20.4V"}],
                contradicting_evidence=[],
                confidence_score=0.72,
                confidence_explanation="Heuristic test score.",
                status="ACTIVE",
                window_start=now,
                window_end=now,
            )
        )
        db.commit()

        ctx = gather_verified_context(
            db=db,
            request=CopilotAskRequest(question="Why did battery voltage drop?", include_live_telemetry=False),
        )
        assert ctx.alert is not None
        assert ctx.alert["alert_id"] == "ALT-UNIFIED1"
        assert ctx.correlation is not None
        assert ctx.correlation["correlation_id"] == "CORR-UNIFIED1"

    # 2. Log an Incident directly from the alert first
    inc_resp = client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "title": "EPS Battery Undervoltage Triage",
            "summary": "Battery voltage dropped below 21.5 V.",
            "subsystem": "battery_power",
            "severity": "CRITICAL",
            "linked_alert_ids": ["ALT-UNIFIED1"],
        },
    )
    assert inc_resp.status_code == 201
    inc_id = inc_resp.json()["incident_id"]

    # 3. Evaluate Copilot recommendation linked to that alert -> auto-binds existing INC without duplicate
    eval_resp = client.post(
        "/api/v1/verification/evaluate",
        headers=headers,
        json=_valid_bat_payload(
            {
                "linked_alert_id": "ALT-UNIFIED1",
                "linked_correlation_id": "CORR-UNIFIED1",
            }
        ),
    )
    assert eval_resp.status_code == 201
    rec_body = eval_resp.json()
    rec_id = rec_body["recommendation_id"]
    assert rec_body["linked_incident_id"] == inc_id

    # 4. Approve recommendation -> records DECISION_RECORDED on the SAME incident
    app_resp = client.post(
        f"/api/v1/decisions/{rec_id}/approve",
        headers=headers,
        json={"notes": "Approved investigative checklist on linked incident."},
    )
    assert app_resp.status_code == 201
    assert app_resp.json()["linked_incident_id"] == inc_id

    # Ensure zero duplicate incidents were created
    all_incs = client.get("/api/v1/incidents", headers=headers).json()
    assert all_incs["total"] == 1

    # Inspect unified incident detail & full timeline
    detail = client.get(f"/api/v1/incidents/{inc_id}", headers=headers).json()
    assert detail["linked_recommendation_id"] == rec_id
    assert "CORR-UNIFIED1" in detail["linked_correlation_ids"]
    assert len(detail["linked_alerts"]) == 1
    assert len(detail["linked_correlations"]) == 1
    assert detail["linked_recommendation"]["latest_decision_status"] == "APPROVED"
    actions = [entry["action"] for entry in detail["logs"]]
    assert "CREATED" in actions
    assert "VERIFICATION_RECORDED" in actions
    assert "DECISION_RECORDED" in actions


def test_socketio_connect_enforces_jwt_and_revocation(
    phase8_client: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import socketio.exceptions
    from app.realtime import socket_manager

    client: TestClient = phase8_client["client"]
    session_factory = phase8_client["session_factory"]

    reg = client.post(
        "/api/v1/auth/register",
        json={"username": "sio_op", "email": "sio@devcore.space", "password": "OperatorPass!2026"},
    ).json()
    token = reg["access_token"]

    monkeypatch.setattr(socket_manager, "SessionLocal", session_factory)
    monkeypatch.setattr(socket_manager, "_status_provider", None)
    monkeypatch.setattr(socket_manager, "_detection_status_provider", None)

    # Anonymous connection refused
    with pytest.raises(socketio.exceptions.ConnectionRefusedError):
        asyncio.run(socket_manager.connect("sid-anon", {}, None))

    # Valid operator JWT accepted
    asyncio.run(socket_manager.connect("sid-valid", {}, {"token": token}))

    # Revoked token refused after logout
    assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    with pytest.raises(socketio.exceptions.ConnectionRefusedError):
        asyncio.run(socket_manager.connect("sid-revoked", {}, {"token": token}))
