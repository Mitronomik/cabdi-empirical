from __future__ import annotations

from fastapi.testclient import TestClient

from app.researcher_api.main import create_app as create_researcher_app


def test_login_rejects_non_allowlisted_origin_header(tmp_path) -> None:
    client = TestClient(create_researcher_app(str(tmp_path / "pilot.sqlite3")))
    response = client.post(
        "/admin/api/v1/auth/login",
        json={"username": "admin", "password": "admin1234"},
        headers={"origin": "https://attacker.example.org"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Cross-origin auth request blocked"


def test_login_allows_local_allowlisted_origin_header(tmp_path) -> None:
    client = TestClient(create_researcher_app(str(tmp_path / "pilot.sqlite3")))
    response = client.post(
        "/admin/api/v1/auth/login",
        json={"username": "admin", "password": "admin1234"},
        headers={"origin": "http://localhost:5174"},
    )
    assert response.status_code == 200
