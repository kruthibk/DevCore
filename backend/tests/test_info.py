"""Tests for /api/v1/info endpoint."""

from fastapi.testclient import TestClient


def test_api_v1_info_returns_mission_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/info")
    assert response.status_code == 200

    data = response.json()
    assert data["application"] == "SAT-TRIAGE"
    assert data["api_version"] == "v1"
    assert data["status"] == "operational"
    assert data["team"]["name"] == "DevCore"
    assert data["team"]["team_id"] == "AV26-BF34B6F9D2"
    assert "11" in data["team"]["problem_statement"]
    assert data["team"]["event"] == "AVISHKAR'26"
