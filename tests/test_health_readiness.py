from __future__ import annotations

from fastapi.testclient import TestClient

from app.participant_api.main import create_app as create_participant_app
from app.researcher_api.main import create_app as create_researcher_app


def test_participant_health_and_readiness(tmp_path) -> None:
    client = TestClient(create_participant_app(str(tmp_path / "pilot.sqlite3")))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["checks"]["database"] == "ok"


def test_participant_readiness_returns_503_on_db_failure(tmp_path) -> None:
    app = create_participant_app(str(tmp_path / "pilot.sqlite3"))
    app.state.store.fetchone = lambda _q, _p: (_ for _ in ()).throw(RuntimeError("db down"))
    client = TestClient(app)

    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["status"] == "not_ready"
    assert ready.json()["checks"]["database"] == "error"


def test_researcher_health_and_readiness(tmp_path) -> None:
    client = TestClient(create_researcher_app(str(tmp_path / "pilot.sqlite3")))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ready = client.get("/ready")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["auth"] == "ok"


def test_researcher_readiness_returns_503_on_db_failure(tmp_path) -> None:
    app = create_researcher_app(str(tmp_path / "pilot.sqlite3"))
    app.state.store.fetchone = lambda _q, _p: (_ for _ in ()).throw(RuntimeError("db down"))
    client = TestClient(app)

    ready = client.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["status"] == "not_ready"
    assert ready.json()["checks"]["database"] == "error"
