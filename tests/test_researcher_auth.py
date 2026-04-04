from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


def test_researcher_routes_require_auth_and_login_logout_cycle(tmp_path) -> None:
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))

    unauthorized = researcher.get("/admin/api/v1/runs")
    assert unauthorized.status_code == 401

    bad_login = researcher.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401

    login = researcher.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert login.status_code == 200
    assert login.json()["ok"] is True

    me = researcher.get("/admin/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True

    authorized = researcher.get("/admin/api/v1/runs")
    assert authorized.status_code == 200

    logout = researcher.post("/admin/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["ok"] is True

    unauthorized_again = researcher.get("/admin/api/v1/runs")
    assert unauthorized_again.status_code == 401


def test_researcher_tampered_session_cookie_fails_cleanly(tmp_path) -> None:
    db_path = str(tmp_path / "pilot.sqlite3")
    researcher = TestClient(create_researcher_app(db_path))
    login = researcher.post("/admin/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert login.status_code == 200

    tampered = researcher.get("/admin/api/v1/auth/me", headers={"Cookie": "researcher_session=tampered.token"})
    assert tampered.status_code == 401
    assert tampered.json()["detail"] == "Invalid or expired researcher session"


def test_participant_public_routes_stay_public_and_researcher_docs_disabled(tmp_path) -> None:
    db_path = str(tmp_path / "pilot.sqlite3")
    participant = TestClient(create_participant_app(db_path))
    researcher = TestClient(create_researcher_app(db_path))

    participant_health = participant.get("/health")
    assert participant_health.status_code == 200

    researcher_docs = researcher.get("/docs")
    assert researcher_docs.status_code == 404
    researcher_openapi = researcher.get("/openapi.json")
    assert researcher_openapi.status_code == 404
